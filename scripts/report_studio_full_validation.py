from __future__ import annotations

from scripts.learning_layer_smoke_test import run_smoke_test as run_learning_layer_smoke_test
from scripts.report_product_layer_smoke_test import run_smoke_test as run_report_product_layer_smoke_test
from scripts.report_services_smoke_test import run_smoke_test as run_report_services_smoke_test
from scripts.report_studio_regression_check import run_regression_check
from scripts.report_studio_service_smoke_test import run_smoke_test as run_report_studio_service_smoke_test


def run_full_validation() -> None:
    run_report_product_layer_smoke_test()
    run_learning_layer_smoke_test()
    run_report_services_smoke_test()
    run_report_studio_service_smoke_test()
    run_regression_check()


if __name__ == "__main__":
    run_full_validation()
    print("full Report Studio validation passed")
