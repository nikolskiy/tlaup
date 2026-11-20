---- MODULE EncSem ----
EXTENDS Naturals
Foo == "café 日本語 😀" + 1
Bar(x) == x
Baz == Bar(1, 2)
Qux == undefinedCafé
====
