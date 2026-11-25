package tlc2.overrides;

/** Its string constants need modified UTF-8: a character beyond the BMP (a surrogate pair) and a NUL (C0 80). */
public class Strings implements ITLCOverrides {
    String emoji = "😀";
    String nul = "a\u0000b";

    @SuppressWarnings("rawtypes")
    @Override
    public Class[] get() {
        return new Class[0];
    }
}
