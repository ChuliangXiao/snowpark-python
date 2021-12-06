from typing import Dict, List, Optional, Tuple, Union

from snowflake.snowpark._internal.analyzer.sf_attribute import Attribute as Attribute
from snowflake.snowpark._internal.sp_expressions import Attribute as SPAttribute
from snowflake.snowpark._internal.sp_types.sp_join_types import JoinType as SPJoinType
from snowflake.snowpark.row import Row
from snowflake.snowpark.types import DataType as DataType

class AnalyzerPackage:
    def result_scan_statement(self, uuid_place_holder: str) -> str: ...
    def function_expression(
        self, name: str, children: List[str], is_distinct: bool
    ) -> str: ...
    def named_arguments_function(self, name: str, args: Dict[str, str]) -> str: ...
    def binary_comparison(self, left: str, right: str, symbol: str) -> str: ...
    def binary_arithmetic_expression(self, op: str, left: str, right: str) -> str: ...
    def alias_expression(self, origin: str, alias: str) -> str: ...
    def limit_expression(self, num: int) -> str: ...
    def grouping_set_expression(self, args: List[List[str]]) -> str: ...
    def like_expression(self, expr: str, pattern: str) -> str: ...
    def regexp_expression(self, expr: str, pattern: str) -> str: ...
    def collate_expression(self, expr: str, collation_spec: str) -> str: ...
    def subfield_expression(self, expr: str, field: Union[str, int]) -> str: ...
    def flatten_expression(
        self, input_: str, path: Optional[str], outer: bool, recursive: bool, mode: str
    ) -> str: ...
    def lateral_statement(self, lateral_expression: str, child: str) -> str: ...
    def join_table_function_statement(self, func: str, child: str) -> str: ...
    def table_function_statement(self, func: str) -> str: ...
    def case_when_expression(
        self, branches: List[Tuple[str, str]], else_value: str
    ) -> str: ...
    def project_statement(
        self, project: List[str], child: str, is_distinct: bool = ...
    ) -> str: ...
    def filter_statement(self, condition, child) -> str: ...
    def sample_statement(
        self,
        child: str,
        probability_fraction: Optional[float] = ...,
        row_count: Optional[int] = ...,
    ): ...
    def aggregate_statement(
        self, grouping_exprs: List[str], aggregate_exprs: List[str], child: str
    ) -> str: ...
    def sort_statement(self, order: List[str], child: str) -> str: ...
    def range_statement(self, start, end, step, column_name) -> str: ...
    def values_statement(self, output: List[SPAttribute], data: List[Row]) -> str: ...
    def empty_values_statement(self, output: List[SPAttribute]): ...
    def set_operator_statement(self, left: str, right: str, operator: str): ...
    def left_semi_or_anti_join_statement(
        self, left: str, right: str, join_type: type, condition: str
    ) -> str: ...
    def snowflake_supported_join_statement(
        self, left: str, right: str, join_type: SPJoinType, condition: str
    ) -> str: ...
    def join_statement(
        self, left: str, right: str, join_type: SPJoinType, condition: str
    ) -> str: ...
    def create_table_statement(
        self, table_name: str, schema: str, replace: bool = ..., error: bool = ...
    ) -> str: ...
    def insert_into_statement(self, table_name: str, child: str) -> str: ...
    def batch_insert_into_statement(
        self, table_name: str, column_names: List[str]
    ) -> str: ...
    def create_table_as_select_statement(
        self, table_name: str, child: str, replace: bool = ..., error: bool = ...
    ) -> str: ...
    def limit_statement(
        self, row_count: str, child: str, on_top_of_order_by: bool
    ) -> str: ...
    def schema_cast_seq(self, schema: List[Attribute]) -> List[str]: ...
    def create_file_format_statement(
        self,
        format_name: str,
        file_type: str,
        options: Dict,
        temp: bool,
        if_not_exist: bool,
    ) -> str: ...
    def file_operation_statement(
        self, command: str, file_name: str, stage_location: str, options: Dict[str, str]
    ) -> str: ...
    def get_options_statement(self, options: Dict[str, str]) -> str: ...
    def select_from_path_with_format_statement(
        self, project: List[str], path: str, format_name: str, pattern: str
    ) -> str: ...
    def unary_minus_expression(self, child: str) -> str: ...
    def not_expression(self, child: str) -> str: ...
    def is_nan_expression(self, child: str) -> str: ...
    def is_null_expression(self, child: str) -> str: ...
    def is_not_null_expression(self, child: str) -> str: ...
    def window_expression(self, window_function: str, window_spec: str) -> str: ...
    def window_spec_expression(
        self, partition_spec: List[str], order_spec: List[str], frame_spec: str
    ) -> str: ...
    def specified_window_frame_expression(
        self, frame_type: str, lower: str, upper: str
    ) -> str: ...
    def window_frame_boundary_expression(
        self, offset: str, is_following: bool
    ) -> str: ...
    def cast_expression(self, child: str, datatype: DataType) -> str: ...
    def order_expression(
        self, name: str, direction: str, null_ordering: str
    ) -> str: ...
    def create_or_replace_view_statement(
        self, name: str, child: str, is_temp: bool
    ) -> str: ...
    def pivot_statement(
        self, pivot_column: str, pivot_values: List[str], aggregate: str, child: str
    ) -> str: ...
    def copy_into_table(
        self,
        table_name: str,
        file_path: str,
        file_format: str,
        format_type_options: Dict[str, str],
        copy_options: Dict[str, str],
        pattern: str,
        *,
        files: Optional[str] = ...,
        validation_mode: Optional[str] = ...,
        column_names: Optional[List[str]] = ...,
        transformations: Optional[List[str]] = ...
    ) -> str: ...
    def create_temp_table_statement(self, table_name: str, schema: str) -> str: ...
    def drop_table_if_exists_statement(self, table_name: str) -> str: ...
    def attribute_to_schema_string(self, attributes: List[Attribute]) -> str: ...
    def schema_value_statement(self, output: List[Attribute]) -> str: ...
    def generator(self, row_count: int) -> str: ...
    def table(self, content: str) -> str: ...
    @classmethod
    def single_quote(cls, value: str) -> str: ...
    @classmethod
    def quote_name(cls, name: str) -> str: ...
    @classmethod
    def validate_quoted_name(cls, name: str) -> str: ...
    @classmethod
    def quote_name_without_upper_casing(cls, name: str) -> str: ...
    @classmethod
    def number(cls, precision: int = ..., scale: int = ...) -> str: ...
