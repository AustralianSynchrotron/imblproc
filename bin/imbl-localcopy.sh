#!/bin/bash
packagedir="$(realpath $0)"
packagedir="$(dirname "$packagedir")"
packagedir="$(dirname "$packagedir")" # to get rid of "bin"
cp -r "$packagedir" .
