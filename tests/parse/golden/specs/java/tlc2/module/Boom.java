package tlc2.module;

import tlc2.value.impl.IntValue;
import tlc2.value.impl.Value;

public class Boom {
    public static Value Boom(final Value v) {
        if (((IntValue) v).val > 1) {
            throw new IllegalStateException("boom from Java override");
        }
        return v;
    }
}
