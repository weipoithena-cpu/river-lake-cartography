# Contributing

Thank you for helping improve River Lake Cartography. Useful contributions include reproducible bug reports, native Windows acceptance, reliable spatial-data import, better label placement and well-documented data sources.

## Development setup

Use an isolated Python environment and install the application's requirements for your actual operating system:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r app/core/assets/requirements.txt
python build_tools/fetch_font.py
python app/main.py --help
```

Start the application with `python app/main.py`. The large Noto font is fetched from its pinned upstream source and verified by hash; it is included in portable/source distribution packages but is not committed as a Git binary. A Windows distribution uses a separate pinned embedded runtime; do not copy Linux `site-packages` into it. Read the command-line help for output-directory and browser options.

Frontend tests require Node.js and the development dependency declared in `package.json`:

```sh
npm install
npm run test:ui
```

Run the Python regression checks using the same interpreter that has the rendering dependencies:

```sh
python tests/data_service_test.py
python tests/test_cartographic_labels.py
python tests/test_integration.py
```

Review each test's actual output. A skipped or mocked check must remain identified as such. Windows acceptance and packaging instructions are in `build_tools/WINDOWS_ACCEPTANCE.md` and `WINDOWS_ACCEPTANCE_PROMPT.txt`.

## Cartographic behavior is part of correctness

Every change must preserve the three adopted rules: river names follow river geometry without leader lines; the legend stays inside the lower-left map frame; and full administrative labels stay inside the correct visible jurisdiction with consistent hierarchy.

Do not make a test pass by removing a requested label, moving real geometry, suppressing an error or declaring an unchecked map approved. If layout cannot succeed at the current extent, report a diagnostic result and explain what can change. A different cartographic mode should be discussed explicitly and tested as a separate, documented behavior.

## Reporting a problem

Include the application version, operating system, input route, steps to reproduce, expected result, actual result and relevant `qa.json` errors. A small shareable GeoJSON/job is more useful than a screenshot alone. Remove credentials, private project paths and confidential monitoring locations before posting. If the failure is online, include the service URL, request extent and observed error/time.

Separate geometry/source problems from layout problems. For administrative errors, identify the affected unit, hierarchy and a verifiable source. For a rendering error, attach both the image and the corresponding configuration when you can share them.

## Pull requests

Keep a change focused. Explain the concrete problem, resulting behavior, relevant tests and remaining limitations. Include a before/after render when label placement or map styling changes. Record source/CRS/license changes explicitly; retain original-source identities and disclose transformations.

Use English for public documentation, comments, interface text and example descriptions. Keep geographical names traceable to the supplied data. Translations and transliterations must not be described as certified official English names without evidence.

## Data and licensing

Contribute only code and data you may redistribute. Application code uses MIT; OSM-derived examples use ODbL and must retain attribution and relevant source information. A code license does not relicense third-party datasets, fonts or libraries. Do not commit build caches, virtual environments, personal output folders, credentials or large distribution ZIPs. Release binaries belong in GitHub Releases.

## What would help most

See [the roadmap](docs/ROADMAP.md). The highest-value work is native Windows/browser verification, robust English river-label placement, and reliable handling of partial online data without obscuring uncertainty.

## Publishing and release maintenance

Maintainers can follow the [first-time publishing guide](docs/PUBLISHING.md) to upload the prepared source tree and either run the supplied test/build/release workflow or attach the prepared preview assets manually. Root `RELEASE_NOTES.md` supplies the release description. Use one publication route for a given tag, preserve the preview status, and keep application versions, tags, source and attached binaries consistent. A successful automated Windows self-test does not replace real-browser visual acceptance.
