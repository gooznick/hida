# HIDA - ng

## Implementation notes

* file should be stored and filtered at the end
* ElaboratedType - keep searching up
* no name - id is the name
* namespace "::" should be converted to none (and not join)
* Add constants !
* Add source string (file::line)
* types ends with "fundamental type" (but uint8_t and __uint8_t can be terminals, too)
* Parsed directly :
  * Typedef
  * Struct
  * Enumeration
  * Variable

## Should support

* basic types 
* Arrays 1-4D
* bool
* All types of pointers (pointers, double pointers, pointers to non POD, function pointers)
* typedefs
* C struct typedefs
* Namespaces
* fixed width types
* Enums
* c++11 enums
* Unions
* bitfields
* Static constants
* packing (#pragma pack)
* wide characters

* Ignore non POD types
* Anonnymous inner structs and unions

## Manipulators

## Converters 

  * python
  * c only
  * endianess swapper

## rejects :

* add scope/namespace list [name may have :: in it, as in struct<std::is_same>]
* if struct has member "incomplete" with value "1" - ignore it
* autoremove system headers sources

- flags in the CLI has errors (source is ommitted by default, regex, cx)
- error message when catxml command fails (+dont remove the temp !)
- constant is not float - not error by default
- remove unknown things (ie !)
- Add -I as a parameter, explicit
- Ignore errors
- Flag to focus + remove others


ERROR: File "setup.py" not found. Directory cannot be installed in editable mode: /home/liaraschafer/dev/p-test/hatch-test
(A "pyproject.toml" file was found, but editable mode currently requires a setup.py based build.)

python -m pip install -U pip setuptools wheel