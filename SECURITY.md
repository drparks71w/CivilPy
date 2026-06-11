# Security Policy

## Supported Versions

Only the latest release of CivilPy receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x (latest) | Yes |
| Earlier | No |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Report vulnerabilities through either of these channels:

1. **Email:** [Dane@daneparks.com](mailto:Dane@daneparks.com) — include "CivilPy Security" in the subject line.
2. **GitLab confidential issue:** Open an issue on the [repository](https://daneparks.com/Dane/civilpy/issues/new)
   and check the "This issue is confidential" box before submitting.

### What to include

- A description of the vulnerability and its potential impact
- Steps to reproduce it
- Any suggested fix if you have one

### Response timeline

You can expect an acknowledgment within 5 business days. Security issues affecting users will be
patched in the next release with a note in the changelog. You will be credited in the changelog
unless you request otherwise.

## Scope

CivilPy is a data processing and calculation library. The primary security concerns are:

- **Arbitrary code execution** via unsafe deserialization, eval, or subprocess calls
- **Path traversal** in file I/O functions
- **Credential exposure** in database connection utilities (`civilpy.general.database_tools`,
  `civilpy.state.ohio.DOT`)
- **Unsafe defaults** in any function that reads external data (PDFs, Excel files, web responses)

Out of scope: vulnerabilities in optional dependencies (PyMuPDF, Selenium, etc.) should be
reported to those projects directly.

---

## Dependency Governance

### Maintainer responsibility

Any maintainer or contributor who introduces a new dependency takes on responsibility for
monitoring that dependency for security issues. This includes:

- Subscribing to the dependency's security advisories (GitHub/GitLab advisory feeds, or the
  project's own security mailing list)
- Reporting relevant vulnerabilities to the CivilPy maintainer promptly
- Proposing an upgrade or removal when a vulnerability is confirmed

Software composition analysis tools such as [Mend](https://www.mend.io/) (formerly WhiteSource)
or [Dependabot](https://docs.github.com/en/code-security/dependabot) are encouraged for automated
advisory monitoring.

### Quarterly dependency review

Dependencies are reviewed on a quarterly basis to assess:

- Whether each dependency is still actively maintained
- Whether newer versions introduce breaking changes or resolve open CVEs
- Whether any dependency can be removed or replaced with a lighter alternative

Reviews are recorded in the project's issue tracker. If you believe a dependency should be
dropped or replaced, open an issue tagged `dependencies` ahead of the next quarterly review.
