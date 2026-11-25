package tlc2.module;

import tlc2.value.impl.IntValue;
import tlc2.value.impl.Value;

public class BoomTrace {
    public static Value BoomTrace(final Value v) {
        if (((IntValue) v).val > 1) {
            throw new StackOverflowError();
        }
        return v;
    }
}
