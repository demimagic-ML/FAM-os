import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.core.contracts import ResultKind, ResultStatus, TaskResult
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.product.storage.cipher import CipherContext
from fam_os.product.storage.contract_payload import decrypt_contract
from fam_os.schemas import SchemaValidationError, encode_document, loads_document
from fam_os.verification import (
    RetrievalCitationsVerification,
    RetrievedSource,
    VerificationDeclaration,
    contract_for_kind,
)
from fam_os.verification.legacy_declarations import (
    RetrievalCitationsVerification as RetrievalCitationsVerificationV1Alpha1,
    VerificationDeclaration as VerificationDeclarationV1Alpha1,
)


class ContractPayloadMigrationTests(unittest.TestCase):
    def test_historical_transitional_result_migrates_only_inside_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(
                root / "fam.sqlite3", os.geteuid(),
            ))
            storage = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            document = encode_document(TaskResult(
                "legacy-result", ResultStatus.COMPLETED, "old answer",
            ))
            document["schema_id"] = "fam.core.task-result/v1alpha1"
            document["contract_version"] = "fam.core/v1alpha1"
            document["payload"]["contract_version"] = "fam.core/v1alpha1"
            del document["payload"]["result_kind"]
            serialized = json.dumps(document, separators=(",", ":"))
            with self.assertRaises(SchemaValidationError):
                loads_document(serialized)
            context = CipherContext(
                "1000", "terminal-result", "legacy-result", "contract",
            )
            token = storage.cipher.encrypt(context, serialized.encode())

            migrated = decrypt_contract(
                storage.cipher, "1000", "terminal-result", "legacy-result",
                token, TaskResult,
            )

            self.assertIsInstance(migrated, TaskResult)
            self.assertEqual(ResultKind.CONVERSATION_ANSWER, migrated.result_kind)
            self.assertEqual("old answer", migrated.content)
            database.close()

    def test_legacy_retrieval_declaration_migrates_readable_but_unbound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(
                root / "fam.sqlite3", os.geteuid(),
            ))
            storage = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            content = "FAM_OS runs locally."
            source = RetrievedSource(
                "source-1", "fixture://source-1", content,
                hashlib.sha256(content.encode()).hexdigest(), "legacy-source-1",
            )
            specification = RetrievalCitationsVerificationV1Alpha1((source,))
            legacy = VerificationDeclarationV1Alpha1(
                "declaration-legacy-retrieval", "legacy-retrieval",
                contract_for_kind(specification.kind), specification,
            )
            serialized = json.dumps(encode_document(legacy), separators=(",", ":"))
            context = CipherContext(
                "1000", "verification-declaration",
                legacy.declaration_id, "contract",
            )
            token = storage.cipher.encrypt(context, serialized.encode())

            migrated = decrypt_contract(
                storage.cipher, "1000", "verification-declaration",
                legacy.declaration_id, token, VerificationDeclaration,
            )

            self.assertIsInstance(migrated.specification, RetrievalCitationsVerification)
            self.assertIsNone(migrated.specification.query)
            database.close()


if __name__ == "__main__":
    unittest.main()
