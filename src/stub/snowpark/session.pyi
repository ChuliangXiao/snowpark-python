from typing import Any, Dict, List, Optional, Tuple, Union

from snowflake.connector import SnowflakeConnection as SnowflakeConnection
from snowflake.connector.options import pandas
from snowflake.snowpark import Column as Column, DataFrame
from snowflake.snowpark._internal.analyzer.sf_attribute import Attribute as Attribute
from snowflake.snowpark._internal.server_connection import ServerConnection
from snowflake.snowpark._internal.sp_types.types_package import (
    ColumnOrName as ColumnOrName,
)
from snowflake.snowpark.dataframe_reader import DataFrameReader
from snowflake.snowpark.file_operation import FileOperation
from snowflake.snowpark.types import StructType
from snowflake.snowpark.udf import UDFRegistration

logger: Any

class Session:
    class SessionBuilder:
        def __init__(self) -> None: ...
        def config(
            self, key: str, value: Union[int, str]
        ) -> Session.SessionBuilder: ...
        def configs(
            self, options: Dict[str, Union[int, str]]
        ) -> Session.SessionBuilder: ...
        def create(self) -> Session: ...
        def __get__(self, obj, objtype: Any | None = ...): ...
    builder: SessionBuilder
    def __init__(self, conn: ServerConnection) -> None: ...
    def close(self) -> None: ...
    def cancel_all(self) -> None: ...
    def getImports(self) -> List[str]: ...
    def addImport(self, path: str, import_path: Optional[str] = ...) -> None: ...
    def removeImport(self, path: str) -> None: ...
    def clearImports(self) -> None: ...
    @property
    def query_tag(self) -> Optional[str]: ...
    @query_tag.setter
    def query_tag(self, tag: str) -> None: ...
    def table(self, name: Union[str, List[str], Tuple[str, ...]]) -> DataFrame: ...
    def table_function(
        self,
        func_name: Union[str, List[str]],
        *func_arguments: ColumnOrName,
        **func_named_arguments: ColumnOrName
    ) -> DataFrame: ...
    def sql(self, query: str) -> DataFrame: ...
    @property
    def read(self) -> DataFrameReader: ...
    def getSessionStage(self) -> str: ...
    def write_pandas(
        self,
        pd: pandas.DataFrame,
        table_name: str,
        *,
        database: Optional[str] = ...,
        schema: Optional[str] = ...,
        chunk_size: Optional[int] = ...,
        compression: str = ...,
        on_error: str = ...,
        parallel: int = ...,
        quote_identifiers: bool = ...,
        auto_create_table: bool = ...
    ) -> DataFrame: ...
    def createDataFrame(
        self,
        data: Union[List, Tuple, pandas.DataFrame],
        schema: Optional[Union[StructType, List[str]]] = ...,
    ) -> DataFrame: ...
    def range(
        self, start: int, end: Optional[int] = ..., step: int = ...
    ) -> DataFrame: ...
    def getDefaultDatabase(self) -> Optional[str]: ...
    def getDefaultSchema(self) -> Optional[str]: ...
    def getCurrentDatabase(self) -> Optional[str]: ...
    def getCurrentSchema(self) -> Optional[str]: ...
    def getFullyQualifiedCurrentSchema(self) -> str: ...
    @property
    def file(self) -> FileOperation: ...
    @property
    def udf(self) -> UDFRegistration: ...
    def flatten(
        self,
        input: ColumnOrName,
        path: Optional[str] = ...,
        outer: bool = ...,
        recursive: bool = ...,
        mode: str = ...,
    ) -> DataFrame: ...
