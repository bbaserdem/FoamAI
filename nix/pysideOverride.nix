# From https://github.com/pyedifice/pyedifice/blob/4c473354a690272856b7ca3da06d7d5d18f7ce81/pyproject-overrides.nix#L6
{pkgs, ...}: final: prev: {
  pyside6-addons = prev.pyside6-addons.overrideAttrs (_old: {
    autoPatchelfIgnoreMissingDeps = [
      "libmysqlclient.so.21"
      "libmimerapi.so"
      "libQt63DQuickLogic.so.6"
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
      pkgs.pcsclite
      pkgs.speechd
    ];
  });
  pyside6-essentials = prev.pyside6-essentials.overrideAttrs (_old: {
    autoPatchelfIgnoreMissingDeps = [
      "libmysqlclient.so.21"
      "libmimerapi.so"
      "libQt6EglFsKmsGbmSupport.so.6"
    ];
    preFixup = ''
      addAutoPatchelfSearchPath ${final.shiboken6}/${final.python.sitePackages}/shiboken6
    '';
    buildInputs = [
      pkgs.kdePackages.full
      pkgs.libxkbcommon
      pkgs.gtk3
      pkgs.speechd
      pkgs.gst
      pkgs.gst_all_1.gst-plugins-base
      pkgs.gst_all_1.gstreamer
      pkgs.postgresql.lib
      pkgs.unixODBC
      pkgs.pcsclite
      pkgs.xorg.libxcb
      pkgs.xorg.xcbutil
      pkgs.xorg.xcbutilcursor
      pkgs.xorg.xcbutilerrors
      pkgs.xorg.xcbutilimage
      pkgs.xorg.xcbutilkeysyms
      pkgs.xorg.xcbutilrenderutil
      pkgs.xorg.xcbutilwm
      pkgs.libdrm
      pkgs.pulseaudio
    ];
  });
}
