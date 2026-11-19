import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import psycopg
from psycopg import sql


class DeviceTypeApiTests(unittest.TestCase):
    """Exercise the real HTTP API in an isolated PostgreSQL schema per test."""

    def setUp(self) -> None:
        self.schema = f"test_{uuid4().hex}"
        with psycopg.connect(connect_timeout=5) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            self.port = address.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.start_server()

    def start_server(self) -> None:
        environment = os.environ.copy()
        environment["PGOPTIONS"] = f"-csearch_path={self.schema}"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
             "127.0.0.1", "--port", str(self.port), "--log-level", "error"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("API process exited during startup")
            try:
                if self.request("GET", "/health")[0] == 200:
                    return
            except (URLError, TimeoutError):
                time.sleep(0.1)
        self.fail("API did not start in time")

    def drop_schema(self) -> None:
        with psycopg.connect(connect_timeout=5) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))
            )

    def stop_server(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def request(self, method: str, path: str, payload: dict | None = None) -> tuple:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_create_read_and_validation(self) -> None:
        self.assertEqual(self.request("GET", "/device-types"), (200, []))
        code, device = self.request("POST", "/device-types", {"name": " device1 "})
        self.assertEqual(code, 201)
        self.assertEqual(device["name"], "device1")
        UUID(device["id"])
        self.assertEqual(self.request("GET", f'/device-types/{device["id"]}'),
                         (200, device))
        self.assertEqual(self.request("GET", "/device-types"), (200, [device]))
        for payload in ({}, {"name": " "}, {"name": 123},
                        {"name": "device", "id": str(uuid4())}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST", "/device-types", payload)[0], 422)
        self.assertEqual(self.request("GET", f"/device-types/{uuid4()}")[0], 404)
        self.assertEqual(self.request("GET", "/device-types/invalid")[0], 422)
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))

    def test_data_survives_restart_and_names_are_stored_safely(self) -> None:
        name = "sensor's device; DROP TABLE device_types; --"
        code, device = self.request("POST", "/device-types", {"name": name})
        self.assertEqual(code, 201)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", f'/device-types/{device["id"]}'),
                         (200, device))
        self.assertEqual(self.request("GET", "/device-types"), (200, [device]))
