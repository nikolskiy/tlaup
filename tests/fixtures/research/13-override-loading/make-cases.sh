#!/usr/bin/env bash
# Usage: make-cases.sh <dest-dir>   -- writes the TLA+ and Java sources of every case under <dest-dir>/cases/
# Each case: spec.tla spec.cfg modules/Ovr.tla java/... ; optional marker files: prop (system property value),
# noprop (do not pass the property), no_classes (compiled classes are left off the classpath)
set -eu
D="$1/cases"
# mk <case> [java-subdir]   (java-subdir defaults to tlc2/overrides; "-" means no java dir)
mk() {
  mkdir -p "$D/$1/modules"
  if [ "${2:-tlc2/overrides}" != "-" ]; then mkdir -p "$D/$1/java/${2:-tlc2/overrides}"; fi
  cat > "$D/$1/spec.tla" <<'T'
---- MODULE spec ----
EXTENDS Naturals, TLC, Ovr
VARIABLE x
Init == x = Add2(1, 2)
Next == x' = x
Inv == PrintT(<<"Inv sees", x, Add2(10, 20)>>)
====
T
  cat > "$D/$1/spec.cfg" <<'T'
INIT Init
NEXT Next
INVARIANT Inv
T
  cat > "$D/$1/modules/Ovr.tla" <<'T'
---- MODULE Ovr ----
EXTENDS Naturals
Add2(a, b) == a + b + 1000
====
T
}
# jv <case> <ClassName>   (body on stdin; package tlc2.overrides)
jv() {
  {
    cat <<'T'
package tlc2.overrides;
import tlc2.value.impl.*;
import tlc2.tool.EvalException;
import tlc2.output.EC;
T
    cat
  } > "$D/$1/java/tlc2/overrides/$2.java"
}
good_get='    @Override public Class[] get() { return new Class[]{ TLCOverrides.class }; }'
add2='    public static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }'
ann='    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)'
annq='    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = false)'

mk ok_warn_true; jv ok_warn_true TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
$add2
$good_get
}
EOT
mk ok_warn_false; jv ok_warn_false TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$annq
$add2
$good_get
}
EOT
mk ok_value_params; jv ok_value_params TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final Value a, final Value b) { return IntValue.gen(((IntValue) a).val + ((IntValue) b).val); }
$good_get
}
EOT
for c in prop_class_not_found prop_class_not_on_classpath prop_second_class_missing; do
  mk $c; jv $c TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
$add2
$good_get
}
EOT
done
echo tlc2.overrides.NoSuchClass > "$D/prop_class_not_found/prop"
touch "$D/prop_class_not_on_classpath/no_classes"
echo "tlc2.overrides.TLCOverrides:tlc2.overrides.NoSuchClass" > "$D/prop_second_class_missing/prop"
mk static_init_throws; jv static_init_throws TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    static { if (true) throw new RuntimeException("boom in static init"); }
$ann
$add2
$good_get
}
EOT
mk ctor_throws; jv ctor_throws TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    public TLCOverrides() { throw new IllegalStateException("boom in constructor"); }
$ann
$add2
$good_get
}
EOT
mk ctor_private; jv ctor_private TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    private TLCOverrides() {}
$ann
$add2
$good_get
}
EOT
mk get_throws; jv get_throws TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @Override public Class[] get() { throw new RuntimeException("boom in get()"); }
}
EOT
mk get_returns_null; jv get_returns_null TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @Override public Class[] get() { return null; }
}
EOT
mk not_itlcoverrides; jv not_itlcoverrides TLCOverrides <<EOT
public class TLCOverrides {
$ann
$add2
    public Class[] get() { return new Class[]{ TLCOverrides.class }; }
}
EOT
mk get_lists_unannotated; jv get_lists_unannotated TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$add2
$good_get
}
EOT
mk annot_module_missing; jv annot_module_missing TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "NoSuchModule", warn = true)
$add2
$good_get
}
EOT
mk annot_op_missing; jv annot_op_missing TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "NoSuchOp", module = "Ovr", warn = true)
    public static Value NoSuchOp(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
$good_get
}
EOT
mk arity_java_fewer; jv arity_java_fewer TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a) { return IntValue.gen(a.val); }
$good_get
}
EOT
mk arity_java_more; jv arity_java_more TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a, final IntValue b, final IntValue c) { return IntValue.gen(a.val + b.val + c.val); }
$good_get
}
EOT
mk param_type_mismatch; jv param_type_mismatch TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final StringValue a, final StringValue b) { return a; }
$good_get
}
EOT
mk return_type_not_value; jv return_type_not_value TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static int Add2(final IntValue a, final IntValue b) { return a.val + b.val; }
$good_get
}
EOT
mk method_not_static; jv method_not_static TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
$good_get
}
EOT
mk method_not_public; jv method_not_public TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
$good_get
}
EOT
mk eval_throws_runtime; jv eval_throws_runtime TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a, final IntValue b) { throw new RuntimeException("boom in override body"); }
$good_get
}
EOT
mk eval_throws_evalexception; jv eval_throws_evalexception TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a, final IntValue b) { throw new EvalException(EC.GENERAL, "boom as EvalException"); }
$good_get
}
EOT
mk eval_returns_null; jv eval_returns_null TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a, final IntValue b) { return null; }
$good_get
}
EOT
mk eval_throws_error; jv eval_throws_error TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
    public static Value Add2(final IntValue a, final IntValue b) { throw new StackOverflowError("boom as Error"); }
$good_get
}
EOT
mk duplicate_override; jv duplicate_override TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$ann
$add2
$ann
    public static Value Add2again(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val + 7); }
$good_get
}
EOT
# legacy convention: class tlc2.module.Ovr, no property, no ITLCOverrides
for c in legacy_ok legacy_op_missing_in_tla legacy_arity_mismatch legacy_throws; do
  mk $c tlc2/module; touch "$D/$c/noprop"
done
cat > "$D/legacy_ok/java/tlc2/module/Ovr.java" <<'EOT'
package tlc2.module;
import tlc2.value.impl.*;
public class Ovr {
    public static Value Add2(final Value a, final Value b) { return IntValue.gen(((IntValue) a).val + ((IntValue) b).val); }
}
EOT
cat > "$D/legacy_op_missing_in_tla/java/tlc2/module/Ovr.java" <<'EOT'
package tlc2.module;
import tlc2.value.impl.*;
public class Ovr {
    public static Value Add2(final Value a, final Value b) { return IntValue.gen(((IntValue) a).val + ((IntValue) b).val); }
    public static Value NotInTla(final Value a) { return a; }
}
EOT
cat > "$D/legacy_arity_mismatch/java/tlc2/module/Ovr.java" <<'EOT'
package tlc2.module;
import tlc2.value.impl.*;
public class Ovr {
    public static Value Add2(final Value a) { return a; }
}
EOT
cat > "$D/legacy_throws/java/tlc2/module/Ovr.java" <<'EOT'
package tlc2.module;
import tlc2.value.impl.*;
public class Ovr {
    public static Value Add2(final Value a, final Value b) { throw new RuntimeException("boom in legacy body"); }
}
EOT
mk annot_module_missing_warn_false; jv annot_module_missing_warn_false TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "NoSuchModule", warn = false)
$add2
$good_get
}
EOT
mk arity_java_fewer_warn_false; jv arity_java_fewer_warn_false TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
$annq
    public static Value Add2(final IntValue a) { return IntValue.gen(a.val); }
$good_get
}
EOT
# index class with a non-default name, selected only through the system property
mk prop_alt_index_class; jv prop_alt_index_class MyOverrides <<EOT
public class MyOverrides implements ITLCOverrides {
$ann
$add2
    @Override public Class[] get() { return new Class[]{ MyOverrides.class }; }
}
EOT
echo tlc2.overrides.MyOverrides > "$D/prop_alt_index_class/prop"
# two index classes in the property, both valid
mk prop_two_index_classes; jv prop_two_index_classes MyOverrides <<EOT
public class MyOverrides implements ITLCOverrides {
$ann
$add2
    @Override public Class[] get() { return new Class[]{ MyOverrides.class }; }
}
EOT
jv prop_two_index_classes TLCOverrides <<EOT
public class TLCOverrides implements ITLCOverrides {
    @Override public Class[] get() { return new Class[]{ }; }
}
EOT
echo tlc2.overrides.TLCOverrides:tlc2.overrides.MyOverrides > "$D/prop_two_index_classes/prop"
mk no_override -; touch "$D/no_override/noprop"
