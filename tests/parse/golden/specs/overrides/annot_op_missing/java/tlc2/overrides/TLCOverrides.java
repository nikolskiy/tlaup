package tlc2.overrides;
import tlc2.value.impl.*;
import tlc2.tool.EvalException;
import tlc2.output.EC;
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "NoSuchOp", module = "Ovr", warn = true)
    public static Value NoSuchOp(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
    @Override public Class[] get() { return new Class[]{ TLCOverrides.class }; }
}
