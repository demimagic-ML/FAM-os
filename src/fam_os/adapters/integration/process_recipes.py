"""Fixed signed process-recipe coordinate and port expansion."""

import re


def recipe_coordinate(value):
    if not isinstance(value, str) or "@" not in value:
        raise ValueError("signed process recipe coordinate is invalid")
    identity, version = value.rsplit("@", 1)
    if not identity or not version:
        raise ValueError("signed process recipe coordinate is invalid")
    return identity, version


def expanded_arguments(template, service):
    ports = {item.name: str(item.requested_host_port) for item in service.ports}
    values = []
    for item in template:
        matches = re.findall(r"\{port:([A-Za-z0-9_.-]+)\}", item)
        if len(matches) == 1 and item.count("{") == item.count("}") == 1:
            name = matches[0]
            if name not in ports:
                raise PermissionError("signed process recipe references an undeclared port")
            values.append(item.replace(f"{{port:{name}}}", ports[name]))
        elif "{" in item or "}" in item:
            raise PermissionError("signed process recipe placeholder is unsupported")
        else:
            values.append(item)
    return tuple(values)
