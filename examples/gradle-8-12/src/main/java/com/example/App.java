package com.example;

import com.google.common.collect.ImmutableList;

public class App {
    public static void main(String[] args) {
        ImmutableList<String> messages = ImmutableList.of("Hello", "from", "Gradle", "cache", "action!");
        System.out.println(String.join(" ", messages));
    }

    public static String greeting() {
        return "Hello, World!";
    }
}
