import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src import agent, gemma_client, snowflake_client


SCHEMA = [
    ("USERS", "USER_ID", "NUMBER"),
    ("USERS", "NAME", "TEXT"),
    ("ORDERS", "ORDER_ID", "NUMBER"),
    ("ORDERS", "USER_ID", "NUMBER"),
]


def model_plan(dataset="USERS"):
    return {
        "status": "success",
        "reason": None,
        "user_intent": "Find user names",
        "information_to_gather": ["user names"],
        "source": "snowflake",
        "dataset": dataset,
        "selection_rationale": "The USERS table contains user names.",
        "sql_query": "SELECT NAME FROM USERS",
    }


class PlanGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.plan_path = Path(self.temp_dir.name) / "latest_plan.json"
        self.path_patcher = patch.object(
            gemma_client, "PLAN_OUTPUT_PATH", self.plan_path
        )
        self.path_patcher.start()
        self.addCleanup(self.path_patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_explicit_dataset_restricts_schema_and_is_persisted(self):
        response = {"message": {"content": json.dumps(model_plan("USERS"))}}
        with patch.object(gemma_client.client, "chat", return_value=response) as chat:
            plan = gemma_client.generate_plan(
                "Find user names", SCHEMA, dataset="USERS"
            )

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Use only this dataset", prompt)
        self.assertIn("return only the aggregate value in the SELECT list", prompt)
        self.assertIn("USERS.NAME", prompt)
        self.assertNotIn("ORDERS.", prompt)
        self.assertEqual(plan, model_plan())
        self.assertEqual(
            json.loads(self.plan_path.read_text(encoding="utf-8")), plan
        )

    def test_ollama_wildcard_bind_host_is_normalized_for_local_client(self):
        self.assertEqual(
            gemma_client._normalize_ollama_host("0.0.0.0:11434"),
            "http://127.0.0.1:11434",
        )

    def test_uploaded_plan_uses_uploaded_source_and_sqlite_compatible_dialect(self):
        plan = model_plan()
        plan["source"] = "uploaded_file"
        plan["sql_query"] = "SELECT COUNT(*) AS USER_COUNT FROM USERS"
        response = {"message": {"content": json.dumps(plan)}}
        with patch.object(gemma_client.client, "chat", return_value=response) as chat:
            result = gemma_client.generate_plan(
                "How many users are there?",
                [("USERS", "NAME", "object")],
                source="uploaded_file",
            )

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("SQLite-compatible SELECT query", prompt)
        self.assertEqual(result["source"], "uploaded_file")

    def test_no_dataset_lets_model_select_from_available_schema(self):
        response = {"message": {"content": json.dumps(model_plan())}}
        with patch.object(gemma_client.client, "chat", return_value=response) as chat:
            plan = gemma_client.generate_plan("Find user names", SCHEMA)

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("No dataset was explicitly provided", prompt)
        self.assertIn("ORDERS.ORDER_ID", prompt)
        self.assertEqual(plan["dataset"], "USERS")

    def test_unavailable_explicit_dataset_is_not_replaced(self):
        with patch.object(gemma_client.client, "chat") as chat:
            plan = gemma_client.generate_plan(
                "Find user names", SCHEMA, dataset="CUSTOMERS"
            )

        chat.assert_not_called()
        self.assertEqual(plan["status"], "error")
        self.assertEqual(plan["dataset"], "CUSTOMERS")
        self.assertEqual(
            json.loads(self.plan_path.read_text(encoding="utf-8")), plan
        )

    def test_malformed_model_output_persists_valid_error_plan(self):
        response = {"message": {"content": "not json"}}
        with patch.object(gemma_client.client, "chat", return_value=response):
            plan = gemma_client.generate_plan("Find user names", SCHEMA)

        self.assertEqual(plan["status"], "error")
        self.assertIsNone(plan["sql_query"])
        self.assertEqual(
            json.loads(self.plan_path.read_text(encoding="utf-8")), plan
        )

    def test_invalid_model_plan_structure_is_rejected(self):
        response = {"message": {"content": json.dumps({"status": "success"})}}
        with patch.object(gemma_client.client, "chat", return_value=response):
            plan = gemma_client.generate_plan("Find user names", SCHEMA)

        self.assertEqual(plan["status"], "error")
        self.assertIn("invalid structure", plan["reason"])

    def test_run_agent_returns_plan_and_persisted_file_path(self):
        plan = {
            "status": "unsupported",
            "reason": "The requested data is not available.",
            "user_intent": "Find a different data source",
            "information_to_gather": [],
            "source": "snowflake",
            "dataset": None,
            "selection_rationale": "No matching dataset was found.",
            "sql_query": None,
        }
        with (
            patch.object(agent, "get_schema_metadata", return_value=SCHEMA),
            patch.object(agent, "generate_plan", return_value=plan) as generate,
            patch.object(agent, "PLAN_OUTPUT_PATH", self.plan_path),
        ):
            result = agent.run_agent(
                "Find a different data source", dataset="MISSING"
            )

        generate.assert_called_once_with(
            "Find a different data source", SCHEMA, "MISSING"
        )
        self.assertEqual(result["plan"], plan)
        self.assertEqual(result["plan_file"], str(self.plan_path))

    def test_plan_is_solvable_with_available_dataset_columns(self):
        can_solve, reason = agent.verify_dataset_compatibility(model_plan(), SCHEMA)

        self.assertTrue(can_solve, reason)

    def test_plan_is_rejected_for_unavailable_dataset_or_column(self):
        unavailable_dataset_plan = model_plan("CUSTOMERS")
        missing_column_plan = model_plan()
        missing_column_plan["sql_query"] = "SELECT EMAIL FROM USERS"

        unavailable_result = agent.verify_dataset_compatibility(
            unavailable_dataset_plan, SCHEMA
        )
        missing_column_result = agent.verify_dataset_compatibility(
            missing_column_plan, SCHEMA
        )

        self.assertFalse(unavailable_result[0])
        self.assertIn("not available", unavailable_result[1])
        self.assertFalse(missing_column_result[0])
        self.assertIn("EMAIL", missing_column_result[1])

    def test_explicit_dataset_rejects_plan_selected_for_other_table(self):
        plan = model_plan("ORDERS")
        plan["sql_query"] = "SELECT ORDER_ID FROM ORDERS"

        can_solve, reason = agent.verify_dataset_compatibility(
            plan, SCHEMA, explicit_dataset="USERS"
        )

        self.assertFalse(can_solve)
        self.assertIn("instead of 'USERS'", reason)

    def test_run_agent_does_not_execute_incompatible_plan(self):
        plan = model_plan()
        plan["sql_query"] = "SELECT EMAIL FROM USERS"
        with (
            patch.object(agent, "get_schema_metadata", return_value=SCHEMA),
            patch.object(agent, "generate_plan", return_value=plan),
            patch.object(agent, "execute_sql") as execute,
            patch.object(agent, "PLAN_OUTPUT_PATH", self.plan_path),
        ):
            result = agent.run_agent("Find user emails")

        execute.assert_not_called()
        self.assertIsNone(result["evidence"])
        self.assertIn("EMAIL", result["answer"])

    def test_multiple_statements_and_qualified_external_tables_are_rejected(self):
        multiple_statements = model_plan()
        multiple_statements["sql_query"] = "SELECT NAME FROM USERS; DROP TABLE USERS"
        qualified_table = model_plan()
        qualified_table["sql_query"] = "SELECT NAME FROM OTHER_DB.USERS"

        self.assertFalse(
            agent.verify_dataset_compatibility(multiple_statements, SCHEMA)[0]
        )
        is_compatible, reason = agent.verify_dataset_compatibility(
            qualified_table, SCHEMA
        )
        self.assertFalse(is_compatible)
        self.assertIn("unqualified", reason)

    def test_verified_query_executes_then_explains_verified_sql_and_evidence(self):
        plan = model_plan()
        evidence = {
            "query_id": "query-123",
            "columns": ["NAME"],
            "rows": [("Ada",)],
        }
        call_order = []

        def execute(sql):
            call_order.append(("execute", sql))
            return evidence

        def explain(question, sql, returned_evidence):
            call_order.append(("explain", question, sql, returned_evidence))
            return "The user is Ada."

        with (
            patch.object(agent, "get_schema_metadata", return_value=SCHEMA),
            patch.object(agent, "generate_plan", return_value=plan),
            patch.object(agent, "execute_sql", side_effect=execute),
            patch.object(agent, "explain_results", side_effect=explain),
            patch.object(agent, "PLAN_OUTPUT_PATH", self.plan_path),
        ):
            result = agent.run_agent("Find user names")

        executed_sql = "SELECT NAME FROM USERS LIMIT 100;"
        self.assertEqual(
            call_order,
            [
                ("execute", executed_sql),
                ("explain", "Find user names", executed_sql, evidence),
            ],
        )
        self.assertEqual(result["answer"], "The user is Ada.")
        self.assertEqual(result["evidence"], evidence)
        self.assertEqual(result["sql_query"], executed_sql)

    def test_explainer_prompt_includes_sql_and_returned_data(self):
        evidence = {
            "query_id": "query-456",
            "columns": ["NAME"],
            "rows": [("Ada",)],
        }
        response = {"message": {"content": "Ada is the result."}}
        with patch.object(gemma_client.client, "chat", return_value=response) as chat:
            answer = gemma_client.explain_results(
                "Find user names", "SELECT NAME FROM USERS LIMIT 100;", evidence
            )

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Executed SQL: SELECT NAME FROM USERS LIMIT 100;", prompt)
        self.assertIn("Data Columns: ['NAME']", prompt)
        self.assertIn("Data Rows: [('Ada',)]", prompt)
        self.assertIn("state its exact value", prompt)
        self.assertIn("do not mention LIMIT", prompt)
        self.assertEqual(answer, "Ada is the result.")

    def test_empty_result_returns_evidence_without_explaining(self):
        evidence = {"query_id": "query-empty", "columns": ["NAME"], "rows": []}
        with (
            patch.object(agent, "get_schema_metadata", return_value=SCHEMA),
            patch.object(agent, "generate_plan", return_value=model_plan()),
            patch.object(agent, "execute_sql", return_value=evidence),
            patch.object(agent, "explain_results") as explain,
            patch.object(agent, "PLAN_OUTPUT_PATH", self.plan_path),
        ):
            result = agent.run_agent("Find user names")

        explain.assert_not_called()
        self.assertEqual(result["evidence"], evidence)
        self.assertEqual(result["sql_query"], "SELECT NAME FROM USERS LIMIT 100;")
        self.assertIn("no records", result["answer"])

    def test_uploaded_csv_dataset_executes_locally_and_summarizes(self):
        plan = model_plan()
        plan.update(
            source="uploaded_file",
            information_to_gather=["user count"],
            sql_query="SELECT COUNT(*) AS USER_COUNT FROM USERS",
        )
        datasets = {
            "USERS": pd.DataFrame({"NAME": ["Ada", "Grace", "Linus"]})
        }
        with (
            patch.object(agent, "generate_plan", return_value=plan),
            patch.object(agent, "explain_results", return_value="There are 3 users."),
            patch.object(agent, "PLAN_OUTPUT_PATH", self.plan_path),
        ):
            result = agent.run_uploaded_agent(
                "How many users are there?", datasets, "USERS"
            )

        self.assertEqual(result["answer"], "The count is 3.")
        self.assertEqual(result["evidence"]["rows"], [(3,)])
        self.assertEqual(result["sql_query"], "SELECT COUNT(*) AS USER_COUNT FROM USERS LIMIT 100;")

    def test_snowflake_aggregate_error_is_explained_actionably(self):
        class SnowflakeAggregateError(Exception):
            errno = 979

        message = agent._snowflake_error_message(SnowflakeAggregateError())
        self.assertIn("non-aggregated column", message)
        self.assertIn("GROUP BY", message)

    def test_scalar_count_summary_uses_exact_database_value(self):
        summary = agent._ground_aggregate_summary(
            "SELECT COUNT(*) FROM USERS LIMIT 100",
            {"columns": ["COUNT(*)"], "rows": [(150000,)]},
            "There are approximately 150,000 users; the limit may truncate the count.",
        )
        self.assertEqual(summary, "The count is 150,000.")


class SchemaMetadataTests(unittest.TestCase):
    def test_metadata_lookup_uses_configured_database_and_schema(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("USERS", "NAME", "TEXT")]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with (
            patch.object(snowflake_client.snowflake.connector, "connect", return_value=connection),
            patch.dict(snowflake_client.SF_CONFIG, {"schema": "ANALYTICS"}),
        ):
            metadata = snowflake_client.get_schema_metadata()

        self.assertEqual(metadata, [("USERS", "NAME", "TEXT")])
        query, parameters = cursor.execute.call_args.args
        self.assertIn("FROM INFORMATION_SCHEMA.COLUMNS", query)
        self.assertIn("table_schema = %s", query)
        self.assertEqual(parameters, ("ANALYTICS",))
        cursor.close.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
