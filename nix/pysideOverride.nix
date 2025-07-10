# From https://github.com/pyedifice/pyedifice/blob/4c473354a690272856b7ca3da06d7d5d18f7ce81/pyproject-overrides.nix#L6
{pkgs, ...}: final: prev: {
  pyside6-addons = prev.pyside6-addons.overridePythonAttrs (_old:
    lib.optionalAttrs stdenv.isLinux {
      autoPatchelfIgnoreMissingDeps = [
        "libmysqlclient.so.21"
        "libmimerapi.so"
      ];
      preFixup = ''
        addAutoPatchelfSearchPath ${final.shiboken6}/${final.python.sitePackages}/shiboken6
        addAutoPatchelfSearchPath ${final.pyside6-essentials}/${final.python.sitePackages}/PySide6
        addAutoPatchelfSearchPath $out/${final.python.sitePackages}/PySide6
      '';
      buildInputs = [
        pkgs.kdePackages.full
        pkgs.nss
        pkgs.xorg.libXtst
        pkgs.alsa-lib
        pkgs.xorg.libxshmfence
        pkgs.xorg.libxkbfile
      ];
    });
}
