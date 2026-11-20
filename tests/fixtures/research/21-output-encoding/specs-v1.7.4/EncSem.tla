---- MODULE EncSem ----
EXTENDS Naturals
Foo == "café 日語文" + 1
Bar(x) == x
Baz == Bar(1, 2)
Qux == undefinedCafé
====
