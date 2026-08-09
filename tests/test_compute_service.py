import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from arcitek_core.compute_service import ComputeQueue, create_server


class ComputeQueueTests(unittest.TestCase):
    def test_rejects_unknown_workload(self):
        queue = ComputeQueue()
        with self.assertRaisesRegex(ValueError, "Unsupported workload"):
            queue.submit("shell", 1000)

    def test_executes_prime_scan(self):
        result = ComputeQueue._execute("prime-scan", 10)
        self.assertEqual(result["primesFound"], 4)


class ComputeServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0, 1)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_endpoint(self):
        with urlopen(f"{self.base_url}/api/health") as response:
            payload = json.load(response)
        self.assertEqual(payload["status"], "operational")

    def test_job_validation(self):
        request = Request(
            f"{self.base_url}/api/jobs",
            data=json.dumps({"workload": "prime-scan", "size": 2}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request)
        self.assertEqual(context.exception.code, 400)


class AuthenticatedComputeServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(
            "127.0.0.1",
            0,
            1,
            api_token="test-control-plane-token",
            principal="authenticated-operator",
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_protected_api_rejects_missing_token(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/api/projects")
        self.assertEqual(context.exception.code, 401)

    def test_authenticated_identity_replaces_caller_supplied_author(self):
        authorization = "Bearer " + "test-control-plane-token"
        request = Request(
            f"{self.base_url}/api/projects",
            data=json.dumps(
                {"name": "Authenticated", "author": "spoofed-user"}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": authorization,
            },
            method="POST",
        )
        with urlopen(request) as response:
            project = json.load(response)["project"]
        revision_request = Request(
            f"{self.base_url}/api/projects/{project['id']}/revisions/1",
            headers={"Authorization": authorization},
        )
        with urlopen(revision_request) as response:
            revision = json.load(response)["revision"]
        self.assertEqual(revision["author"], "authenticated-operator")


if __name__ == "__main__":
    unittest.main()
