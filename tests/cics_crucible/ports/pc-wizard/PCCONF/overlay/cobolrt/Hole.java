package com.gitgalaxy.modernized.cobolrt;

/** Thrown by the translator's output for a statement it did not translate ("line N: statement"). */
public class Hole extends RuntimeException {
    private static final long serialVersionUID = 1L;

    public Hole(String message) {
        super(message);
    }
}
