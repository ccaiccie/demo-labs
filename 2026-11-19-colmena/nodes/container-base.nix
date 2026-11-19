# Shared base for every lab node: NixOS running as a Docker container with systemd.
{ modulesPath, lib, ... }:
{
  imports = [ "${modulesPath}/virtualisation/docker-image.nix" ];

  # SSH is how Colmena reaches the nodes (key-only root login, lab key)
  services.openssh.enable = true;
  services.openssh.settings = {
    PermitRootLogin = "prohibit-password";
    PasswordAuthentication = false;
  };
  users.users.root.openssh.authorizedKeys.keyFiles = [ ../keys/lab_ed25519.pub ];

  # Docker gives the container its address and resolver
  networking.useDHCP = false;
  documentation.enable = false;
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  system.stateVersion = "26.05";
}
