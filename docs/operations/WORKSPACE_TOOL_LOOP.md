# Workspace tool loop

FAM_OS can now inspect a selected local folder, retrieve relevant files, propose
a bounded plan, show exact diffs, apply only an approved change, re-observe the
result, and offer a verified reversal.

## Use it from Console

1. Start the installed service and open the authenticated Console launcher.
2. In **Your workspace**, choose **Open folder**, navigate below your home
   directory, select the project, and choose **Use folder**.
3. Submit an outcome that explicitly requests implementation, for example:

   ```text
   Inspect this project, create a bounded plan to correct the greeting in
   src/app.py, and implement the plan.
   ```

4. Read the Tool terminal. It must show workspace map and retrieval evidence,
   not a model-written shell command.
5. Review the approval card. It contains the plan, exact relative paths, before
   and after SHA-256 digests, and unified diffs. Files are unchanged at this
   point.
6. Approve or deny. Approval applies the exact proposal; denial changes
   nothing.
7. A successful result says the workspace patch was independently verified and
   lists the approved plan and verified changed files. The activity lane shows
   execution, re-observation, and verification.
8. Use **Undo** when offered to preview and approve restoration of the exact
   prior bytes. Undo is refused if another process changed a patched file.

## Safety bounds

- Workspace authority comes from the selected folder URI, never from prompt
  text alone.
- Recursive mapping scans at most six levels, 128 directories, and 512 files.
- Generated/build/cache directories and symlinks are not traversed.
- Retrieval reads at most 16 UTF-8 documents, 32 KiB each and 64 KiB total.
- A proposal changes one to four existing retrieved UTF-8 files, at most 32 KiB
  each and 64 KiB total.
- File paths and expected hashes are bound by Core to retrieval evidence.
- Every write uses the scoped atomic adapter; partial multi-file failure rolls
  back prior writes.
- No unrestricted shell, PTY, or model-generated command is executed.

## Interpreting failures

- **Capability unavailable** means no selected workspace/action surface matched
  the request. Re-select the folder and refresh the machine view.
- **Action parameters invalid** means the expert did not return the strict plan
  and complete-file JSON contract. No file changed.
- **Precondition changed** means a proposed file changed after observation.
  Submit a fresh request so FAM can re-observe it.
- **Postcondition failed** means independent hash verification did not match.
  The result is withheld and recovery evidence remains visible.
- A response labeled **model answer - no machine action** did not edit the
  workspace, regardless of commands shown in its prose.

## Current limitation

This loop edits existing text files. New files, deletion, arbitrary commands,
package installation, and general terminal automation require separate typed
capabilities and are not inferred from an implementation prompt.
