#!/usr/bin/env python3
#
# Copyright (c) 2012-2022 Snowflake Computing Inc. All rights reserved.
#
import functools
import os
import sys
import time
from logging import getLogger
from typing import IO, Any, Dict, Iterator, List, Optional, Set, Union

import snowflake.connector
from snowflake.connector import SnowflakeConnection, connect
from snowflake.connector.constants import FIELD_ID_TO_NAME
from snowflake.connector.cursor import ResultMetadata, SnowflakeCursor
from snowflake.connector.errors import NotSupportedError, ProgrammingError
from snowflake.connector.network import ReauthenticationRequest
from snowflake.connector.options import pandas
from snowflake.snowpark._internal.analyzer.analyzer_utils import (
    escape_quotes,
    quote_name,
    quote_name_without_upper_casing,
)
from snowflake.snowpark._internal.analyzer.datatype_mapper import str_to_sql
from snowflake.snowpark._internal.analyzer.expression import Attribute
from snowflake.snowpark._internal.analyzer.schema_utils import (
    convert_result_meta_to_attribute,
)
from snowflake.snowpark._internal.analyzer.snowflake_plan import (
    BatchInsertQuery,
    SnowflakePlan,
)
from snowflake.snowpark._internal.error_message import SnowparkClientExceptionMessages
from snowflake.snowpark._internal.telemetry import TelemetryClient
from snowflake.snowpark._internal.utils import (
    get_application_name,
    get_version,
    is_in_stored_procedure,
    normalize_local_file,
    normalize_remote_file_or_dir,
    result_set_to_iter,
    result_set_to_rows,
    unwrap_stage_location_single_quote,
)
from snowflake.snowpark.query_history import QueryHistory, QueryRecord
from snowflake.snowpark.row import Row

logger = getLogger(__name__)

# set `paramstyle` to qmark for batch insertion
snowflake.connector.paramstyle = "qmark"

# parameters needed for usage tracking
PARAM_APPLICATION = "application"
PARAM_INTERNAL_APPLICATION_NAME = "internal_application_name"
PARAM_INTERNAL_APPLICATION_VERSION = "internal_application_version"


def _build_target_path(stage_location: str, dest_prefix: str = "") -> str:
    qualified_stage_name = unwrap_stage_location_single_quote(stage_location)
    dest_prefix_name = (
        dest_prefix
        if not dest_prefix or dest_prefix.startswith("/")
        else f"/{dest_prefix}"
    )
    return f"{qualified_stage_name}{dest_prefix_name if dest_prefix_name else ''}"


def _build_put_statement(
    local_path: str,
    stage_location: str,
    dest_prefix: str = "",
    parallel: int = 4,
    compress_data: bool = True,
    source_compression: str = "AUTO_DETECT",
    overwrite: bool = False,
) -> str:
    target_path = normalize_remote_file_or_dir(
        _build_target_path(stage_location, dest_prefix)
    )
    parallel_str = f"PARALLEL = {parallel}"
    compress_str = f"AUTO_COMPRESS = {str(compress_data).upper()}"
    source_compression_str = f"SOURCE_COMPRESSION = {source_compression.upper()}"
    overwrite_str = f"OVERWRITE = {str(overwrite).upper()}"
    final_statement = f"PUT {local_path} {target_path} {parallel_str} {compress_str} {source_compression_str} {overwrite_str}"
    return final_statement


class ServerConnection:
    class _Decorator:
        @classmethod
        def wrap_exception(cls, func):
            def wrap(*args, **kwargs):
                # self._conn.is_closed()
                if args[0]._conn.is_closed():
                    raise SnowparkClientExceptionMessages.SERVER_SESSION_HAS_BEEN_CLOSED()
                try:
                    return func(*args, **kwargs)
                except ReauthenticationRequest as ex:
                    raise SnowparkClientExceptionMessages.SERVER_SESSION_EXPIRED(
                        ex.cause
                    )
                except Exception as ex:
                    raise ex

            return wrap

        @classmethod
        def log_msg_and_perf_telemetry(cls, msg):
            def log_and_telemetry(func):
                @functools.wraps(func)
                def wrap(*args, **kwargs):
                    logger.debug(msg)
                    start_time = time.perf_counter()
                    result = func(*args, **kwargs)
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    sfqid = result["sfqid"] if result and "sfqid" in result else None
                    # If we don't have a query id, then its pretty useless to send perf telemetry
                    if sfqid:
                        args[0]._telemetry_client.send_upload_file_perf_telemetry(
                            func.__name__, duration, sfqid
                        )
                    logger.debug(f"Finished in {duration:.4f} secs")

                return wrap

            return log_and_telemetry

    def __init__(
        self,
        options: Dict[str, Union[int, str]],
        conn: Optional[SnowflakeConnection] = None,
    ) -> None:
        self._lower_case_parameters = {k.lower(): v for k, v in options.items()}
        self._add_application_name()
        self._conn = conn if conn else connect(**self._lower_case_parameters)
        if "password" in self._lower_case_parameters:
            self._lower_case_parameters["password"] = None
        self._cursor = self._conn.cursor()
        self._telemetry_client = TelemetryClient(self._conn)
        self._query_listener: Set[QueryHistory] = set()
        # The session in this case refers to a Snowflake session, not a
        # Snowpark session
        self._telemetry_client.send_session_created_telemetry(not bool(conn))

    def _add_application_name(self) -> None:
        if PARAM_APPLICATION not in self._lower_case_parameters:
            self._lower_case_parameters[PARAM_APPLICATION] = get_application_name()
        if PARAM_INTERNAL_APPLICATION_NAME not in self._lower_case_parameters:
            self._lower_case_parameters[
                PARAM_INTERNAL_APPLICATION_NAME
            ] = get_application_name()
        if PARAM_INTERNAL_APPLICATION_VERSION not in self._lower_case_parameters:
            self._lower_case_parameters[
                PARAM_INTERNAL_APPLICATION_VERSION
            ] = get_version()

    def add_query_listener(self, listener: QueryHistory) -> None:
        self._query_listener.add(listener)

    def remove_query_listener(self, listener: QueryHistory) -> None:
        self._query_listener.remove(listener)

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def is_closed(self) -> bool:
        return self._conn.is_closed()

    @_Decorator.wrap_exception
    def get_session_id(self) -> int:
        return self._conn.session_id

    def get_default_database(self) -> Optional[str]:
        return (
            quote_name(self._lower_case_parameters["database"])
            if "database" in self._lower_case_parameters
            else None
        )

    def get_default_schema(self) -> Optional[str]:
        return (
            quote_name(self._lower_case_parameters["schema"])
            if "schema" in self._lower_case_parameters
            else None
        )

    @_Decorator.wrap_exception
    def _get_current_parameter(self, param: str, quoted: bool = True) -> Optional[str]:
        name = getattr(self._conn, param) or self._get_string_datum(
            f"SELECT CURRENT_{param.upper()}()"
        )
        return (
            (quote_name_without_upper_casing(name) if quoted else escape_quotes(name))
            if name
            else None
        )

    def _get_string_datum(self, query: str) -> Optional[str]:
        rows = result_set_to_rows(self.run_query(query)["data"])
        return rows[0][0] if len(rows) > 0 else None

    @SnowflakePlan.Decorator.wrap_exception
    def get_result_attributes(self, query: str) -> List[Attribute]:
        return convert_result_meta_to_attribute(self._cursor.describe(query))

    @_Decorator.log_msg_and_perf_telemetry("Uploading file to stage")
    def upload_file(
        self,
        path: str,
        stage_location: str,
        dest_prefix: str = "",
        parallel: int = 4,
        compress_data: bool = True,
        source_compression: str = "AUTO_DETECT",
        overwrite: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if is_in_stored_procedure():
            file_name = os.path.basename(path)
            target_path = _build_target_path(stage_location, dest_prefix)
            try:
                # upload_stream directly consume stage path, so we don't need to normalize it
                self._cursor.upload_stream(
                    open(path, "rb"), f"{target_path}/{file_name}"
                )
            except ProgrammingError as pe:
                tb = sys.exc_info()[2]
                ne = SnowparkClientExceptionMessages.SQL_EXCEPTION_FROM_PROGRAMMING_ERROR(
                    pe
                )
                raise ne.with_traceback(tb) from None
        else:
            uri = normalize_local_file(path)
            return self.run_query(
                _build_put_statement(
                    uri,
                    stage_location,
                    dest_prefix,
                    parallel,
                    compress_data,
                    source_compression,
                    overwrite,
                )
            )

    @_Decorator.log_msg_and_perf_telemetry("Uploading stream to stage")
    def upload_stream(
        self,
        input_stream: IO[bytes],
        stage_location: str,
        dest_filename: str,
        dest_prefix: str = "",
        parallel: int = 4,
        compress_data: bool = True,
        source_compression: str = "AUTO_DETECT",
        overwrite: bool = False,
    ) -> Optional[Dict[str, Any]]:
        uri = normalize_local_file(f"/tmp/placeholder/{dest_filename}")
        try:
            if is_in_stored_procedure():
                input_stream.seek(0)
                target_path = _build_target_path(stage_location, dest_prefix)
                try:
                    # upload_stream directly consume stage path, so we don't need to normalize it
                    self._cursor.upload_stream(
                        input_stream, f"{target_path}/{dest_filename}"
                    )
                except ProgrammingError as pe:
                    tb = sys.exc_info()[2]
                    ne = SnowparkClientExceptionMessages.SQL_EXCEPTION_FROM_PROGRAMMING_ERROR(
                        pe
                    )
                    raise ne.with_traceback(tb) from None
            else:
                return self.run_query(
                    _build_put_statement(
                        uri,
                        stage_location,
                        dest_prefix,
                        parallel,
                        compress_data,
                        source_compression,
                        overwrite,
                    ),
                    file_stream=input_stream,
                )
        # If ValueError is raised and the stream is closed, we throw the error.
        # https://docs.python.org/3/library/io.html#io.IOBase.close
        except ValueError as ex:
            if input_stream.closed:
                raise SnowparkClientExceptionMessages.SERVER_UDF_UPLOAD_FILE_STREAM_CLOSED(
                    dest_filename
                )
            else:
                raise ex

    def notify_query_listeners(self, query_record: QueryRecord) -> None:
        for listener in self._query_listener:
            listener._add_query(query_record)

    @_Decorator.wrap_exception
    def run_query(
        self,
        query: str,
        to_pandas: bool = False,
        to_iter: bool = False,
        is_ddl_on_temp_object: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            # Set SNOWPARK_SKIP_TXN_COMMIT_IN_DDL to True to avoid DDL commands to commit the open transaction
            if is_ddl_on_temp_object:
                if not kwargs.get("_statement_params"):
                    kwargs["_statement_params"] = {}
                kwargs["_statement_params"]["SNOWPARK_SKIP_TXN_COMMIT_IN_DDL"] = True
            results_cursor = self._cursor.execute(query, **kwargs)
            self.notify_query_listeners(
                QueryRecord(results_cursor.sfqid, results_cursor.query)
            )
            logger.debug(f"Execute query [queryID: {results_cursor.sfqid}] {query}")
        except Exception as ex:
            query_id_log = f" [queryID: {ex.sfqid}]" if hasattr(ex, "sfqid") else ""
            logger.error(f"Failed to execute query{query_id_log} {query}\n{ex}")
            raise ex

        # fetch_pandas_all/batches() only works for SELECT statements
        # We call fetchall() if fetch_pandas_all/batches() fails,
        # because when the query plan has multiple queries, it will
        # have non-select statements, and it shouldn't fail if the user
        # calls to_pandas() to execute the query.
        if to_pandas:
            try:
                data_or_iter = (
                    map(
                        self._fix_pandas_df_integer,
                        results_cursor.fetch_pandas_batches(),
                    )
                    if to_iter
                    else self._fix_pandas_df_integer(results_cursor.fetch_pandas_all())
                )
            except NotSupportedError:
                data_or_iter = (
                    iter(results_cursor) if to_iter else results_cursor.fetchall()
                )
            except KeyboardInterrupt:
                raise
            except BaseException as ex:
                raise SnowparkClientExceptionMessages.SERVER_FAILED_FETCH_PANDAS(
                    str(ex)
                )
        else:
            data_or_iter = (
                iter(results_cursor) if to_iter else results_cursor.fetchall()
            )

        return {"data": data_or_iter, "sfqid": results_cursor.sfqid}

    def execute(
        self,
        plan: SnowflakePlan,
        to_pandas: bool = False,
        to_iter: bool = False,
        **kwargs,
    ) -> Union[
        List[Row], "pandas.DataFrame", Iterator[Row], Iterator["pandas.DataFrame"]
    ]:
        result_set, result_meta = self.get_result_set(
            plan, to_pandas, to_iter, **kwargs
        )
        if to_pandas:
            return result_set
        else:
            if to_iter:
                return result_set_to_iter(result_set, result_meta)
            else:
                return result_set_to_rows(result_set, result_meta)

    @SnowflakePlan.Decorator.wrap_exception
    def get_result_set(
        self,
        plan: SnowflakePlan,
        to_pandas: bool = False,
        to_iter: bool = False,
        **kwargs,
    ) -> Union[
        List[Any],
        "pandas.DataFrame",
        SnowflakeCursor,
        Iterator["pandas.DataFrame"],
        List[ResultMetadata],
    ]:
        action_id = plan.session._generate_new_action_id()

        result, result_meta = None, None
        try:
            placeholders = {}
            for i, query in enumerate(plan.queries):
                if isinstance(query, BatchInsertQuery):
                    self.run_batch_insert(query.sql, query.rows, **kwargs)
                else:
                    final_query = query.sql
                    for holder, id_ in placeholders.items():
                        final_query = final_query.replace(holder, id_)
                    result = self.run_query(
                        final_query,
                        to_pandas,
                        to_iter and (i == len(plan.queries) - 1),
                        is_ddl_on_temp_object=query.is_ddl_on_temp_object,
                        **kwargs,
                    )
                    placeholders[query.query_id_place_holder] = result["sfqid"]
                    result_meta = self._cursor.description
                if action_id < plan.session._last_canceled_id:
                    raise SnowparkClientExceptionMessages.SERVER_QUERY_IS_CANCELLED()
        finally:
            # delete created tmp object
            for action in plan.post_actions:
                self.run_query(
                    action.sql,
                    is_ddl_on_temp_object=action.is_ddl_on_temp_object,
                    **kwargs,
                )

        if result is None:
            raise SnowparkClientExceptionMessages.SQL_LAST_QUERY_RETURN_RESULTSET()

        return result["data"], result_meta

    def get_result_and_metadata(
        self, plan: SnowflakePlan, **kwargs
    ) -> Union[List[Row], List[Attribute]]:
        result_set, result_meta = self.get_result_set(plan, **kwargs)
        result = result_set_to_rows(result_set)
        meta = convert_result_meta_to_attribute(result_meta)
        return result, meta

    @_Decorator.wrap_exception
    def run_batch_insert(self, query: str, rows: List[Row], **kwargs) -> None:
        # with qmark, Python data type will be dynamically mapped to Snowflake data type
        # https://docs.snowflake.com/en/user-guide/python-connector-api.html#data-type-mappings-for-qmark-and-numeric-bindings
        params = [list(row) for row in rows]
        query_tag = (
            kwargs["_statement_params"]["QUERY_TAG"]
            if "_statement_params" in kwargs
            and "QUERY_TAG" in kwargs["_statement_params"]
            and not is_in_stored_procedure()
            else None
        )
        if query_tag:
            set_query_tag_cursor = self._cursor.execute(
                f"alter session set query_tag = {str_to_sql(query_tag)}"
            )
            self.notify_query_listeners(
                QueryRecord(set_query_tag_cursor.sfqid, set_query_tag_cursor.query)
            )
        results_cursor = self._cursor.executemany(query, params)
        self.notify_query_listeners(
            QueryRecord(results_cursor.sfqid, results_cursor.query)
        )
        if query_tag:
            unset_query_tag_cursor = self._cursor.execute(
                "alter session unset query_tag"
            )
            self.notify_query_listeners(
                QueryRecord(unset_query_tag_cursor.sfqid, unset_query_tag_cursor.query)
            )
        logger.debug("Execute batch insertion query %s", query)

    def _fix_pandas_df_integer(self, pd_df: "pandas.DataFrame") -> "pandas.DataFrame":
        for column_metadata, pandas_dtype, pandas_col_name in zip(
            self._cursor.description, pd_df.dtypes, pd_df.columns
        ):
            if (
                FIELD_ID_TO_NAME.get(column_metadata.type_code) == "FIXED"
                and column_metadata.precision is not None
                and column_metadata.scale == 0
                and not str(pandas_dtype).startswith("int")
            ):
                pd_df[pandas_col_name] = pandas.to_numeric(
                    pd_df[pandas_col_name], downcast="integer"
                )
        return pd_df
