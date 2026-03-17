{
  description = "arxiv-sanity-lite";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python311
            pkgs.python311Packages.pip
            pkgs.python311Packages.virtualenv
          ];

          shellHook = ''
            if [ ! -d .venv ]; then
              echo "Creating venv..."
              python -m venv .venv
            fi
            source .venv/bin/activate

            if [ ! -f .venv/.installed ]; then
              echo "Installing dependencies..."
              pip install -q -r requirements.txt
              touch .venv/.installed
            fi

            echo "arxiv-sanity-lite ready"
          '';
        };
      }
    );
}
