import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_engine_and_cleaning import test_engine_schema_and_query, test_data_quality_detection
from tests.test_sql_security import test_sql_security_valid_queries, test_sql_security_forbidden_queries
from tests.test_fix_operations import test_remove_duplicate_rows, test_standardize_text_format, test_fill_missing_value, test_execute_approved_fix_validation
from tests.test_safe_eval import test_safe_arithmetic_evaluation, test_safe_functions, test_security_rejections
from tests.test_storage_and_undo import test_session_lifecycle_and_undo
from tests.test_expanded_operations import test_custom_calculated_column, test_split_column, test_regex_extract, test_replace_value_mapping, test_remove_outliers
from tests.test_dictionary_prompt import test_data_dictionary_and_few_shot
from tests.test_auth_and_rbac import test_password_hashing_and_verification, test_jwt_token_lifecycle, test_user_manager_and_roles, test_tenant_session_scoping

def run_tests():
    print("1. Running Engine & Cleaning tests...")
    test_engine_schema_and_query()
    test_data_quality_detection()
    print("   [PASS] Engine & Cleaning tests passed!")

    print("2. Running SQL Security tests...")
    test_sql_security_valid_queries()
    test_sql_security_forbidden_queries()
    print("   [PASS] SQL Security tests passed!")

    print("3. Running Fix Operations tests...")
    test_remove_duplicate_rows()
    test_standardize_text_format()
    test_fill_missing_value()
    test_execute_approved_fix_validation()
    print("   [PASS] Fix Operations tests passed!")

    print("4. Running Safe AST Evaluation tests...")
    test_safe_arithmetic_evaluation()
    test_safe_functions()
    test_security_rejections()
    print("   [PASS] Safe AST Evaluation tests passed!")

    print("5. Running Storage & Undo tests...")
    test_session_lifecycle_and_undo()
    print("   [PASS] Storage & Undo tests passed!")

    print("6. Running Expanded Operations tests...")
    test_custom_calculated_column()
    test_split_column()
    test_regex_extract()
    test_replace_value_mapping()
    test_remove_outliers()
    print("   [PASS] Expanded Operations tests passed!")

    print("7. Running Data Dictionary & Few-Shot tests...")
    test_data_dictionary_and_few_shot()
    print("   [PASS] Data Dictionary & Few-Shot tests passed!")

    print("8. Running Auth & RBAC Multi-Tenant tests...")
    test_password_hashing_and_verification()
    test_jwt_token_lifecycle()
    test_user_manager_and_roles()
    test_tenant_session_scoping()
    print("   [PASS] Auth & RBAC Multi-Tenant tests passed!")

    print("\nALL 8 TEST SUITES (PHASE 1, 1.5, & PHASE 2) PASSED 100% CLEANLY!")

if __name__ == "__main__":
    run_tests()
