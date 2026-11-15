package tlc2.overrides;
import tlc2.value.impl.*;
import tlc2.tool.EvalException;
import tlc2.output.EC;
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2(final StringValue a, final StringValue b) { return a; }
    @Override public Class[] get() { return new Class[]{ TLCOverrides.class }; }
}
