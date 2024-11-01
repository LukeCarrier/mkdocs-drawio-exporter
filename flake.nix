{
  description = "mkdocs-drawio-exporter";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  };

  outputs = { flake-utils, nixpkgs, ... }:
  flake-utils.lib.eachDefaultSystem (system: {
    devShells.default =
      let
        pkgs = import nixpkgs { inherit system; };
      in
        pkgs.mkShell {
          packages = with pkgs; [
            drawio
            poetry
            python312
            python312Packages.python-lsp-server
          ];
        };
  });
}
