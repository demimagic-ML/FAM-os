"""Durable enabled state for signed release expert runtime bindings."""

from fam_os.core.production.contracts import RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelProvenance
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.contract_payload import encrypt_contract
from fam_os.product.storage.contract_payload import decrypt_contract
from fam_os.product.storage.database import ProductionDatabase


class SqliteExpertEnablementRepository:
    def __init__(
        self, database: ProductionDatabase, cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        self._database: ProductionDatabase = database
        self._cipher: ProductPayloadCipher = cipher
        self._owner_id = owner_id

    def synchronize(
        self,
        provenance: RuntimeModelProvenance,
        model: RuntimeModelEntry,
    ) -> None:
        token = encrypt_contract(
            self._cipher, self._owner_id, "expert-state", provenance.expert_id, model,
        )
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT state FROM expert_state WHERE expert_id=?",
                (provenance.expert_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO expert_state VALUES (?,?,?,?,?,"
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                    (
                        provenance.expert_id, provenance.package_ref,
                        provenance.runtime_binding_ref, "enabled", token,
                    ),
                )
                return
            connection.execute(
                "UPDATE expert_state SET package_ref=?,runtime_binding_ref=?,"
                "details_ciphertext=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE expert_id=?",
                (
                    provenance.package_ref, provenance.runtime_binding_ref,
                    token, provenance.expert_id,
                ),
            )

    def enabled_expert_ids(self) -> set[str]:
        rows = self._database.fetchall(
            "SELECT expert_id FROM expert_state WHERE state='enabled' ORDER BY expert_id"
        )
        return {value for row in rows if isinstance((value := row[0]), str)}

    def set_enabled(self, expert_id: str, enabled: bool) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE expert_state SET state=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE expert_id=?",
                ("enabled" if enabled else "disabled", expert_id),
            )
            return cursor.rowcount == 1

    def enabled_models(
        self,
    ) -> tuple[tuple[RuntimeModelProvenance, RuntimeModelEntry], ...]:
        rows = self._database.fetchall(
            "SELECT expert_id,package_ref,runtime_binding_ref,details_ciphertext "
            "FROM expert_state WHERE state='enabled' ORDER BY expert_id",
        )
        values = []
        for expert_id, package_ref, binding_ref, token in rows:
            if (
                not isinstance(expert_id, str)
                or not isinstance(package_ref, str)
                or not isinstance(binding_ref, str)
                or not isinstance(token, str)
            ):
                raise TypeError("stored expert enablement row is invalid")
            model = decrypt_contract(
                self._cipher, self._owner_id, "expert-state", expert_id,
                token, RuntimeModelEntry,
            )
            if not isinstance(model, RuntimeModelEntry):
                raise TypeError("stored enabled model is invalid")
            values.append((RuntimeModelProvenance(
                model.model_ref, expert_id, package_ref, binding_ref,
                model.intents, model.verifier_ids,
            ), model))
        return tuple(values)
