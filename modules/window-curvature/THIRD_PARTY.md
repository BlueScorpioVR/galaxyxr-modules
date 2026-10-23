# Third-party components

- **Frida / frida-inject 17.23.3**, unmodified Android arm64 binary.
  Source: https://github.com/frida/frida/tree/17.23.3 and
  https://github.com/frida/frida-core/tree/17.23.3
  License: wxWindows Library Licence 3.1 (LGPL-2.0-or-later with exception).
  The build includes upstream COPYING and the full LGPL-2.0-or-later text
  from SPDX license-list-data v3.27.0.
- **frida-java-bridge 7.0.13**, bundled unmodified source through Frida Compiler.
  Source: https://github.com/frida/frida-java-bridge/tree/7.0.13
  npm: https://registry.npmjs.org/frida-java-bridge/-/frida-java-bridge-7.0.13.tgz
  License: LGPL-2.0 WITH WxWindows-exception-3.1, per npm package metadata.
  The original npm archive is included under bin/third-party/ for source availability.

Frida inject archive SHA256:
fa27b0478fbe1909978388d606236008c40e19ffddcea3bca69a6ed54fde02dc

Decompressed frida-inject SHA256:
bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122

frida-java-bridge npm SHA512 (base64):
YSyKjxbxKnSi3KSUy9vciOvTOuq0RRh9dkxzkQVEdfIIZlw20zE8D3Cq9eL2FDqUVj4YKas6Wf09kCjL5zbffg==

ECJ, D8 and Android compile stubs are build tools only and are not shipped as
runtime libraries. Their input hashes are recorded in bin/source/helper-build.json.
