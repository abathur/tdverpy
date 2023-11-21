{ pkgs ? import <nixpkgs> {} }:

pkgs.python3.pkgs.buildPythonPackage rec {
  version = "0.0.0";
  name = "tdverpy-unreleased";
  src = ./.;
  # src = fetchFromGitHub {
  #   owner = "abathur";
  #   repo = "tdverpy";
  #   rev = "c0ef630a2b2bc283221b293ac057d57100182f02";
  #   sha256 = "0swn2p2fwifvvvi9b1xz2kjq5pwimxffwy9dsa99w1ks944gzs4n";
  # };

  prePatch = ''
    substituteAllInPlace setup.cfg
  '';
  buildInputs = [ ];

  propagatedBuildInputs = with pkgs.python3.pkgs; [
    pygit2
    pyyaml
  ];

  # pygit2 tests need this on ubuntu
  SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";

  meta = {
    homepage = "https://github.com/abathur/tdverpy";
    license = pkgs.lib.licenses.mit;
    description = "A WIP implementation of the ideas in github.com/abathur/tdver";
  };
}
