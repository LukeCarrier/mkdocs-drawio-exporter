{
  description = "mkdocs-drawio-exporter";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  };

  outputs = { flake-utils, nixpkgs, ... }:
  flake-utils.lib.eachDefaultSystem (system: rec {
    devShells.default =
      let
        pkgs = import nixpkgs { inherit system; };
        fhs = pkgs.buildFHSUserEnv {
          name = "fhs-shell";
          targetPkgs = pkgs: [
            pkgs.drawio
            pkgs.nil
            pkgs.poetry
            pkgs.python312
            pkgs.python312Packages.python-lsp-server
          ];
          runScript = "bash";
        };
      in
        fhs.env;
  });
}
