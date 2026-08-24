"""Best-effort complete retirement of process integration resources."""


def retire_process_resources(
    *, stop, units, secrets, root, secret_roots, network, document, permit,
):
    errors = []
    try:
        stop(units)
    except BaseException as error:
        errors.append(error)
    try:
        secret_evidence = secrets.cleanup(root, secret_roots)
    except BaseException as error:
        errors.append(error); secret_evidence = ()
    try:
        usage = network.close(document, permit)
    except BaseException as error:
        errors.append(error); usage = None
    if errors:
        raise RuntimeError("process resource retirement was incomplete") from errors[-1]
    return secret_evidence, usage
