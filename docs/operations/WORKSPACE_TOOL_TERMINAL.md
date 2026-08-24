# Workspace and Tool terminal

## Purpose

The Console workbench lets the owner grant one local folder or file to a task
and inspect what FAM_OS actually observed or executed. It is the everyday entry
point for deterministic local tools; it is not an unrestricted web terminal.

## Use

1. Open FAM Console through the authenticated launcher.
2. Select **Open folder** in the left workbench.
3. Enter or navigate to a directory beneath the current owner's home folder.
4. Select **Use this folder**. The exact folder URI becomes the task resource.
5. Ask a bounded question such as `List the top-level files in this folder.`
6. Select a file in the workspace list to make that exact file the task
   resource, then ask for a summary or review.
7. Inspect **Tool terminal** for capability IDs, paths, outputs, receipt IDs,
   and action status.

Simple listings use exact observation rendering and do not invoke a model.
Explanations and analysis can invoke an expert using the observed content.

## Actions

`Create folder Ivan` while a folder is selected resolves beneath that selected
folder. Console must present the proposal for approval. Core then verifies the
directory postcondition and releases a verified receipt; reversal removes only
the exact created directory when it remains empty and identity-matched.

Configured project tools, such as a fixed test command, retain their existing
allowlisted executable and arguments. The Tool terminal has no arbitrary
command prompt, does not execute Markdown code blocks, and does not inherit a
shell environment.

## Bounds

- Folder navigation is rooted at the owner's home directory.
- Symlink traversal and paths outside that root are denied.
- Directory listings are capped at 256 entries.
- An owner-filesystem file observation is capped at 256 KiB.
- Observation authority does not imply write or execution authority.
- A model response without an action receipt means no machine action occurred.

