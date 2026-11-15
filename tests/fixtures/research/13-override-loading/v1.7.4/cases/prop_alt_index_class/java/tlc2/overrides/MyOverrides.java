package tlc2.overrides;
import tlc2.value.impl.*;
import tlc2.tool.EvalException;
import tlc2.output.EC;
public class MyOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
    @Override public Class[] get() { return new Class[]{ MyOverrides.class }; }
}
