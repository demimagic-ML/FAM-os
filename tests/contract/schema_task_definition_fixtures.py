from fam_os.core.engineering import EngineeringTaskDefinition, engineering_task_digest
from tests.contract.schema_engineering_fixtures import NOW, engineering_schema_values


def task_definition_schema_values() -> tuple[object, ...]:
    task = engineering_schema_values()[0]
    return (EngineeringTaskDefinition(
        f"definition-{task.task_id}", task, "acceptance-engineering-1",
        NOW, engineering_task_digest(task),
    ),)
