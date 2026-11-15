package tlc2.module;
import tlc2.value.impl.*;
public class Ovr {
    public static Value Add2(final Value a, final Value b) { return IntValue.gen(((IntValue) a).val + ((IntValue) b).val); }
    public static Value NotInTla(final Value a) { return a; }
}
