# hive.nix: three NixOS "network appliances" managed by Colmena
let
  addr = {
    router1 = "10.88.0.11";
    dns1 = "10.88.0.12";
    monitor1 = "10.88.0.13";
  };
  dnsRecords = builtins.fromJSON (builtins.readFile ./data/dns-records.json);
  firewall = builtins.fromJSON (builtins.readFile ./data/firewall.json);
in
{
  meta = {
    nixpkgs = import (import ./nixpkgs.nix) { localSystem = "x86_64-linux"; };
    description = "Colmena network lab";
  };

  # Applied to every node
  defaults = { name, pkgs, lib, ... }: {
    imports = [ ./nodes/container-base.nix ];
    networking.hostName = name;
    deployment = {
      targetHost = addr.${name};
      targetUser = "root";
    };

    # nftables firewall: SSH, plus node_exporter only from the lab subnet
    networking.firewall.enable = lib.mkForce true;
    networking.nftables.enable = true;
    networking.firewall.checkReversePath = false;  # WSL kernel lacks nft fib
    networking.firewall.allowedTCPPorts = [ 22 ] ++ firewall.${name}.tcp;
    networking.firewall.allowedUDPPorts = firewall.${name}.udp;
    networking.firewall.extraInputRules = ''
      ip saddr 10.88.0.0/24 tcp dport 9100 accept
    '';

    services.prometheus.exporters.node.enable = true;
    environment.systemPackages = with pkgs; [ dig tcpdump curl ];
  };

  router1 = { ... }: {
    deployment.tags = [ "edge" ];
    # Dummy lab key: uploaded over SSH at deploy time, never put in the Nix store
    deployment.keys."snmp-community" = {
      keyFile = ./secrets/snmp-community.txt;
      destDir = "/run/keys";
      permissions = "0400";
    };

    # Edge filter: drop anything from addresses in the blocklist set
    networking.nftables.tables.edge = {
      family = "inet";
      content = ''
        set blocklist {
          type ipv4_addr
          elements = { 198.51.100.77, 203.0.113.50 }
        }
        chain input {
          type filter hook input priority -10; policy accept;
          ip saddr @blocklist counter drop
        }
      '';
    };
  };

  dns1 = { lib, ... }: {
    deployment.tags = [ "dns" ];
    services.unbound = {
      enable = true;
      settings.server = {
        interface = [ "0.0.0.0" ];
        access-control = [ "10.88.0.0/24 allow" ];
        local-zone = [ ''"lab." static'' ];
        local-data = lib.mapAttrsToList (n: ip: ''"${n}.lab. A ${ip}"'') dnsRecords;
      };
    };
  };

  monitor1 = { lib, ... }: {
    deployment.tags = [ "monitoring" ];
    # The unit asks for PrivateUsers, which this unprivileged container cannot set up
    systemd.services.prometheus.serviceConfig.PrivateUsers = lib.mkForce false;
    services.prometheus = {
      enable = true;
      globalConfig.scrape_interval = "10s";
      scrapeConfigs = [{
        job_name = "nodes";
        static_configs = [{ targets = lib.mapAttrsToList (n: ip: "${ip}:9100") addr; }];
      }];
    };
  };
}
