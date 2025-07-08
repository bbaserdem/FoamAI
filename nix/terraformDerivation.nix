# We don't use the nixpkgs variant because it wants to compile from source if not cached.
# our caching is rate limited by github and as such it is extremly painful when rate limiting
# is invoked because it forces a compilation from source. Nixpkgs does not make a binary variant
# available like vault-bin, so we go fetch this directly from hashicorp
{pkgs, ...}:
pkgs.stdenv.mkDerivation {
  pname = "terraform";
  version = "1.9.8";
  src = pkgs.fetchzip {
    url =
      if pkgs.stdenv.isDarwin
      then "https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_darwin_arm64.zip"
      else "https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip";
    sha256 =
      if pkgs.stdenv.isDarwin
      then "0pf0ppqxspkan417wrr5kbd6vbb4s1l98fzca5ssb4hdydibvijw"
      else "0bpl60bi05pinw7jq305qlgmavsnw37r6rzc7n5gncxhqysysh9j";
    stripRoot = false;
  };
  installPhase = ''
    mkdir -p $out/bin
    mv terraform $out/bin/
    chmod +x $out/bin/terraform
  '';
}
