# Pinned nixpkgs (nixos-26.05 channel), used by the image build and the hive
builtins.fetchTarball {
  url = "https://github.com/NixOS/nixpkgs/archive/f68407657ad294471eb4b2e65d193df26edf729f.tar.gz";
  sha256 = "1956vsp8b0nj2hg9llwk5ad4diz9dw2159camzfydvy2z40wpr8k";
}
