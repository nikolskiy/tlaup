package tlc2.overrides;

/** Implements nothing; the string fooled the old regex, which stripped "//" comments. */
public class NotAnOverride {
    String u = "http://x"; // implements ITLCOverrides
}
