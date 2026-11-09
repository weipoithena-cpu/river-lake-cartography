# Publish this project to GitHub: first-time guide

This guide explains how **you** can upload the prepared English materials and publish a downloadable Windows preview. No repository or release was published by preparing this kit. The addresses below describe the intended destination after you create it.

## 1. Extract the publishing kit

Download the publishing-kit ZIP supplied with this delivery and extract it completely. Open the extracted folder in Windows File Explorer.

| Kit item | Use |
|---|---|
| `01_GitHub_Repository` | Files and folders that belong in the GitHub repository |
| `02_Release_Assets` | Complete Windows ZIP, complete source ZIP and `SHA256SUMS.txt` for a release |
| `START_HERE` instructions | Quick orientation supplied with the kit |

Keep the two numbered folders separate. Repository files make the project readable and editable online. Release assets provide downloadable programs.

**Upload the contents of `01_GitHub_Repository`, not the enclosing numbered folder and not its ZIP.** The Windows distribution is roughly 70 MB and belongs under **Releases**, not in the ordinary source-file upload.

The large Noto font is intentionally omitted from the lean repository folder. Source developers retrieve the pinned font with `python build_tools/fetch_font.py`; the portable Windows ZIP and prepared source ZIP include it. Do not copy the font, runtime or distribution ZIPs into the repository folder to “complete” it.

## 2. Create an empty public repository

Sign in to GitHub in your browser, then open [the new-repository page](https://github.com/new). Use these values:

| Field | Value for this project |
|---|---|
| Owner | `weipoithena-cpu` |
| Repository name | `river-lake-cartography` |
| Description | `Portable river and lake cartography workbench with traceable data and rule-driven labeling for presentation maps.` |
| Visibility | Public |
| Generate README | Off |
| Generate `.gitignore` | None/off |
| Choose a license | None/off |

The kit already supplies README, ignore rules and MIT license files. Leave GitHub's generation options off to start with an empty destination. Select **Create repository**. GitHub's [new-repository documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository) describes the current form.

The intended repository address is:

`https://github.com/weipoithena-cpu/river-lake-cartography`

If that name is already occupied, inspect the existing repository before doing anything with it. Do not replace unrelated work. Either use the intended existing empty project or choose another name and update the repository links in the documentation. If you use another account, update the owner portion as well.

## 3. Upload the source tree through the browser

On the empty repository page, follow the link for uploading existing files. In a repository that already has a file listing, use **Add file → Upload files**.

In File Explorer, open `01_GitHub_Repository`. Select **all its contents**, including the directories and dot-prefixed entries, and drag that selection into GitHub's upload area. The selection should include `app`, `build_tools`, `docs`, `tests`, `validation`, `.github`, `.gitignore`, `.gitattributes` and the root documents.

Check the upload list before committing. The paths must start with names such as `README.md`, `app/main.py` and `.github/workflows/validate-and-build.yml`. They must **not** start with `01_GitHub_Repository/`. If an unwanted outer folder appears, remove that pending upload and repeat from inside the numbered folder.

Use a commit message such as:

```text
Add English River Lake Cartography preview
```

Commit the initial files to the repository's `main` branch. This workflow expects that branch name. If your account created a differently named default branch, rename it before the Actions steps: open the branch selector, choose **View all branches**, open the menu beside the default branch, choose **Rename branch**, and enter `main`. See GitHub's [branch-renaming guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/renaming-a-branch).

GitHub's browser uploader currently allows at most 100 files in one upload and 25 MiB per file. The prepared lean repository is intended for that route. If you add extra files and exceed the count, upload in batches while preserving paths. The ordinary web uploader does not apply `.gitattributes` transformations; the supplied files are already prepared. See [GitHub's file-upload instructions](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

### Check the repository after the commit

Open the **Code** tab and verify:

- `README.md` is at the root and its project overview renders beneath the file list.
- The English example image displays.
- `app/main.py`, `build_tools/assemble_windows.py` and `docs/PUBLISHING.md` open as readable files.
- `.github/workflows/validate-and-build.yml` exists with exactly that nested path.
- `LICENSE`, `CONTRIBUTING.md`, `RELEASE_NOTES.md` and `VALIDATION.md` are present.
- No enclosing `01_GitHub_Repository` directory, full `runtime` folder or distribution ZIP appears in the source tree.

Uploading a source ZIP as a single file would not produce this structure and would not activate the workflow. The first repository upload normally starts a validation/build run; **that automatic push-triggered run does not publish a release**.

## 4. Recommended route: let Actions test Windows and publish

This route builds a fresh Windows package from the uploaded source and runs the actual EXE on a Windows runner before releasing it. You do not need to install Python or Git on your computer to use this browser workflow.

### First inspect the automatic run

1. Open the repository's **Actions** tab.
2. Select **Validate and build**.
3. Open the run created by the initial upload and wait for it to finish.
4. Check both the Linux checks and the **Actual Windows executable self-test** job.

If there is no automatic run because the initial branch had another name, manually run this workflow on `main` with `publish_release` left **off**. That performs validation and packaging without creating a release.

If a job fails, open its failed step and read the error. Do not describe the package as Windows-tested on the basis of a failed or skipped job. A network/download failure may be transient; a code, hash or test failure needs investigation. The Windows and Linux validation artifacts retain useful evidence.

The original delivery already passed **34 Linux-side regression checks** and an English example self-test, but its preparation environment did **not** run the native Windows executable. A successful GitHub Windows job adds native automated evidence for the newly built artifact. It still does not replace opening the browser interface and visually inspecting it on a real Windows desktop.

### Run the release-enabled workflow

After the source is correct and the initial checks are satisfactory:

1. In **Actions → Validate and build**, select **Run workflow**.
2. Select branch `main`.
3. Turn on the input labeled **Publish the tested build as a public preview release** (`publish_release = true`).
4. Leave the release-tag input as `v1.0.0-preview.1` for this unchanged first release.
5. Start the workflow and wait for the Linux, Windows and release jobs to finish.

The workflow is already configured with `workflow_dispatch` and the necessary job-level publication permission. You do not need to paste a personal access token into a document or create a secret for this supplied workflow. Repository or organization policy can still restrict Actions; follow an actual reported policy issue rather than bypassing it.

GitHub explains the workflow controls in [Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). A manual-run control requires the workflow file on the default branch and write access to the repository.

The release job waits for both test/build jobs. It also checks that the tag equals `v` plus the application's version and refuses to overwrite an existing release. The new release uses the artifacts from that same run and is marked as a **pre-release**.

### Verify the published result

Open the repository's **Releases** area. The version page should list:

- `RiverLakeCartography-Windows-x64.zip`
- `RiverLakeCartography-Source.zip`
- `SHA256SUMS.txt`

Download the Windows asset to confirm the link works. Extract the entire ZIP and run `RiverLakeCartography.exe` with its adjacent `app` and `runtime` folders intact. Run the bundled example and inspect its image. For deeper acceptance, use `WINDOWS_ACCEPTANCE_PROMPT.txt` and the bundled check command.

Keep the validation evidence associated with the run. If the workflow rebuilds a package, use **its** checksum file with **its** assets; do not mix a new ZIP with the older kit's checksum.

## 5. Alternative route: manually publish the supplied assets

Use this route if you want to publish the already-prepared preview files yourself. **Choose either this route or the Actions publication route for a given tag. Do not perform both for `v1.0.0-preview.1`.** The workflow intentionally refuses to replace a release that already exists.

The supplied assets remain a preview with Linux verification and Windows static checks unless you separately complete native acceptance. Do not claim that merely uploading these files runs a Windows test. If you changed application code after extracting the kit, rebuild the assets first or use the recommended Actions route so the released binaries correspond to the source.

Open the repository's **Releases** section and choose **Draft a new release**. Set:

| Release field | Value |
|---|---|
| New tag | `v1.0.0-preview.1` |
| Target | The `main` commit containing this unchanged kit |
| Title | `River Lake Cartography v1.0.0-preview.1` |
| Description | Paste the contents of root `RELEASE_NOTES.md` |
| Pre-release | Enabled |

Attach the two ZIP files and `SHA256SUMS.txt` from `02_Release_Assets` in the release's asset area. Wait until each upload completes. Review the names and sizes, then publish. GitHub's [release-management guide](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) documents these controls. If your repository uses immutable releases, finish attaching the assets in the draft before publishing.

The Windows ZIP contains the working program. GitHub may also display its automatically generated “Source code” archives. Those automatic source archives are not the portable application and do not substitute for the Windows asset. The separately prepared `RiverLakeCartography-Source.zip` includes the font and reproducible build material.

### Optional download-integrity check on Windows

In PowerShell, switch to the folder containing the downloaded files and run:

```powershell
Get-FileHash -Algorithm SHA256 .\RiverLakeCartography-Windows-x64.zip
```

Compare the displayed hash with the matching filename in `SHA256SUMS.txt`. Uppercase and lowercase letters are equivalent. This confirms that the downloaded bytes match the listed package; it is not a substitute for runtime acceptance.

## 6. What to share with other people

Once the repository and release actually exist, share the repository address for code, background and contributions. Share the version's release page for ordinary Windows downloads.

Tell recipients to download the **Windows x64 ZIP**, extract it completely and keep all its parts together. They do not need an installed Python environment or Codex to run the portable application. For feedback, ask them to use **Issues** with the version, steps, relevant quality report and a shareable example. Contributors can fork the repository, make a focused change and submit a pull request according to `CONTRIBUTING.md`.

No GitHub Pages deployment is required: this is a desktop application distributed through Releases, not a hosted website.

## 7. Later updates and versions

For documentation-only corrections, edit/upload the relevant source files and commit a clear description. For application changes, use a new version and build/test the new source before publishing new binaries.

Version values must remain consistent across the application's `VERSION` in `app/main.py`, `APP_VERSION` in `build_tools/assemble_windows.py`, `package.json`, release notes/change log and the workflow's default release-tag input. Update other user-facing version references as appropriate. For example, a future `1.0.0-preview.2` application needs tag `v1.0.0-preview.2`.

**Changing only the tag input is insufficient.** The release job rejects a tag that does not match the application's build version. Do not replace an older version's assets with different program contents; create a new version so reports and checksums remain meaningful.

## 8. Common first-upload problems

| Symptom | What to check |
|---|---|
| README is inside an extra numbered folder | The enclosing folder was uploaded; source files need to be at repository root |
| No “Validate and build” workflow | Confirm `.github/workflows/validate-and-build.yml` was uploaded and is on the default branch |
| No manual-run button | Open the named workflow, confirm the default-branch file has `workflow_dispatch`, and use an account with write access |
| Windows ZIP is rejected by ordinary file upload | Attach it as a Release asset, not as a source file |
| Initial run has no release | Expected: push-triggered validation does not publish; manually enable publication or use the manual-release alternative |
| Release job says the tag mismatches | Use the supplied tag for unchanged version 1, or update the application version consistently for a new version |
| Release already exists | Open it; do not repeat both publication routes or attempt to replace assets automatically |
| Source checkout reports a missing font | Run `python build_tools/fetch_font.py`; the build/CI route also retrieves it |
| Program does not run when only the EXE is copied | Extract the complete Windows ZIP with `app` and `runtime` adjacent |

Keep the exact error and the relevant run URL when requesting help. The project can then be improved from concrete evidence rather than assumptions about what failed.
