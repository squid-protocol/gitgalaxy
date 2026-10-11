      * CEEIGZCT stand-in (GitGalaxy-written, NOT IBM's member).
      * Declares only the symbolic feedback code CRECUST tests: CEE000, the
      * first 8 bytes of a Language Environment condition token for "the
      * service completed successfully" (severity 0, message 0, all zero).
      * Source: IBM z/OS Language Environment documentation, "Using symbolic
      * feedback codes" and the CEEIGZCT description; see oracle register L4.
      * Used only where the estate has no CEEIGZCT of its own.
           88 CEE000 VALUE X'0000000000000000'.
