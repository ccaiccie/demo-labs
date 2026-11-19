# Builds the bootstrap image: plain NixOS with sshd and the lab key, nothing else.
# Usage: nix-build image/default.nix && docker import result/tarball/*.tar.xz colmena-lab/nixos-base
let
  nixpkgs = import ../nixpkgs.nix;
  nixos = import "${nixpkgs}/nixos" {
    system = "x86_64-linux";
    configuration = { networking.hostName = "nixos-base"; imports = [ ../nodes/container-base.nix ]; };
  };
in nixos.config.system.build.tarball
