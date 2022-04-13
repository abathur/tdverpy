{ pkgs ? import <nixpkgs> { } }:

with pkgs;
let
  tdver = callPackage ./default.nix { };
  demo = pkgs.resholve.writeScript "demo.sh" {
    interpreter = "${bash}/bin/bash";
    inputs = [ tdver git coreutils ];
    execer = [
      "cannot:${git}/bin/git"
      "cannot:${tdver}/bin/tdver"
    ];
  } (builtins.readFile ./demo.sh);
in
pkgs.mkShell {
  buildInputs = [ tdver ];
  shellHook = ''
    echo ${demo}
    ${demo}
    exit
  '';
}
