package tlc2.overrides;
import tlc2.value.impl.*;
import tlc2.tool.EvalException;
import tlc2.output.EC;
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2again(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val + 7); }
    @Override public Class[] get() { return new Class[]{ TLCOverrides.class }; }
}
