---
layout: post
title:  "Complexity trade-offs in `ruby-cldr`"
date:   2022-04-12 09:00:00 -0000
tags: ruby i18n unicode cldr trade-offs
---

CLDR defines several mechanisms for keys to inheriting values from other keys:

* Locale Inheritance
* Lateral Inheritance
* Aliases

and defines an algorithm that clients can use to resolve any key in the CLDR data to a value.

However, some clients are not capable of handling all of these mechanisms, so the data must be "flattened" for them.
This can be costly in terms of the RAM used to store duplicate values, but allows for simpler clients, and faster lookups from the data.

## Locale Inheritance

CLDR defines an inheritance hierarchy for locales.

For example, `es-MX` ("Mexican Spanish") inherits from `es-419` ("Latin American Spanish") which inherits from `es` ("International Spanish").
Further, CLDR defines a `root` locale that all top-level locales inherit from, so `es` inherits from `root`.

If a key isn't present in the data for a particular locale, the client is supposed to fall back through the inheritance chain, and look for that key in each parent locale in turn.

This allows the data to be defined once in the CLDR dataset, avoiding duplication.

### Example

Let's imagine that we have a simple set of files in 4 locales: `en-CA`, `en-US`, `en`, `root`.


`en-CA.yml`:

```yaml
joe: Joe's favourite colour is grey
```

`en-US.yml`:

```yaml
joe: Joe's favorite color is gray
```

`en.yml`:

```yaml
james: James' favorite color is mauve.
```

`root.yml`:

```yaml
mass-kilogram:
  other: "%{count} kg"
```

The CLDR v41 data defines the locale inheritance chain for `en-CA` as `en-CA` -> `en` -> `root`, so when a key isn't found in the `en-CA` file, the client is supposed to fall back through the inheritance chain, and look for that key in `en`, then in `root`.

### Flattening

But what if your client either cannot, or does not want to, fall back through locales?:

* Perhaps it's a legacy client that doesn't understand CLDR's locale fallbacks, or is stuck using an old version of the inheritance hierarchy.
* Perhaps the performance penalty for making multiple lookups is prohibitive.

In that case, you might want to "flatten" the data so that the values for every key are present in every locale with no fallbacks required. Effectively, flattening involves iterating over every available key and doing the resolution of the key in each locale.

`en-CA.yml`:

```yaml
joe: Joe's favourite colour is grey
james: James' favorite color is mauve. # From `en.yml`
mass-kilogram:
  other: "%{count} kg" # From `root.yml`
```

`en-US.yml`:

```yaml
joe: Joe's favorite color is gray
james: James' favorite color is mauve. # From `en.yml`
mass-kilogram:
  other: "%{count} kg" # From `root.yml`
```

`en.yml`:

```yaml
james: James' favorite color is mauve.
mass-kilogram:
  other: "%{count} kg" # From `root.yml`
```

`root.yml`:

```yaml
mass-kilogram:
  other: "%{count} kg"
```

Now resolving a key is a single lookup. The key is either present in the first locale the client looks at, or it isn't present in any locale in the inheritance chain.

This might work for a small number of locales and a small number of keys, but this duplication of values at every level of the locale inheritance chain consumes a prohibitively expensive amount of memory once you have thousands of keys in hundreds (or thousands) of locales.

CLDR v41 has 414 locales and over 100000000000000 (TODO) strings. It's 100 MiB (TODO) on disk without duplication. Flattening all of the keys into each locale makes this size balloon to 100000000000000 MiB (TODO)! 📈💥

Thankfully, `ruby-i18n/i18n`'s [`I18n::Backend::Fallbacks`](https://github.com/ruby-i18n/i18n/blob/master/lib/i18n/backend/fallbacks.rb) understands how to fallback through the locales (defined in `I18n.fallbacks`), so no flattening is needed and the memory overhead of the duplicated strings is avoided.

## Lateral Inheritance

However, Locale Inheritance is not the only form of inheritance defined by CLDR.
Eagle-eyed readers familiar with i18n might have noticed that the `mass-kilogram` key in `root` is missing the `one` key needed for pluralization lookups to succeed in `en` locales.

This is a case of ["Lateral Inheritance"](http://www.unicode.org/reports/tr35/#Lateral_Inheritance), where a pluralization key will only be present in a locale if it differs from the value of the `other` pluralization key.

So a lookup of `mass-kilogram.one` in `en-CA` should first fallback to `mass-kilogram.other` before falling back to other locales:

1. `en-CA.mass-kilogram.one`
2. `en-CA.mass-kilogram.other`
3. `en.mass-kilogram.one`
4. `en.mass-kilogram.other`
5. `root.mass-kilogram.one`
6. `root.mass-kilogram.other`

`ruby-i18n/i18n`'s [`I18n::Backend::Pluralization`](https://github.com/ruby-i18n/i18n/blob/master/lib/i18n/backend/pluralization.rb) unfortunately doesn't understand Lateral Inheritance, so flattening of pluralization value is necessary to make pluralization work when inheriting from parent locales. This involves flattening the `other` key, then duplicating it fill in any missing pluralization keys needed for the locale.

`en-CA.yml`:

```
mass-kilogram:
  other: "%{count} kg" # Copied from `root.yml`'s `mass-kilogram.other`
  one: "%{count} kg" # Copied from `mass-kilogram.other` (which in turn was copied from `root.yml`'s `mass-kilogram.other`)
```

If/when [this PR](https://github.com/ruby-i18n/i18n/pull/634) is merged, it will at least know enough to inherit from the `other` key.

### Other Lateral Inheritance attributes

In CLDR's terminology, pluralization keys use the `count` attribute, but there are also other attributes used in Lateral Inheritance.

Other examples of attributes include `gender` (e.g., "feminine", "neuter") and `case` (e.g., "accusative", "nominative"), but there [are others](http://www.unicode.org/reports/tr35/#Lateral_Inheritance) too.

Multiple Lateral Inheritance attributes can even be used together, leading to long lookup chains that check every combination:

1. `key` (count="few", gender="feminine", case="accusative")
1. `key` (count="few", gender="feminine", case="nominative")
1. `key` (count="few", gender="feminine")
1. `key` (count="few", gender="neuter", case="accusative")
1. `key` (count="few", gender="neuter", case="nominative")
1. `key` (count="few", gender="neuter")
1. `key` (count="few", case="accusative")
1. `key` (count="few", case="nominative")
1. `key` (count="few")
1. `key` (count="other", gender="feminine", case="accusative")
1. `key` (count="other", gender="feminine", case="nominative")
1. `key` (count="other", gender="feminine")
1. `key` (count="other", gender="neuter", case="accusative")
1. `key` (count="other", gender="neuter", case="nominative")
1. `key` (count="other", gender="neuter")
1. `key` (count="other", case="accusative")
1. `key` (count="other", case="nominative")
1. `key` (count="other")
1. `key` (gender="feminine", case="accusative")
1. `key` (gender="feminine", case="nominative")
1. `key` (gender="feminine")
1. `key` (gender="neuter", case="accusative")
1. `key` (gender="neuter", case="nominative")
1. `key` (gender="neuter")
1. `key` (case="accusative")
1. `key` (case="nominative")
1. `key`

Again, `ruby-i18n/i18n` has no concept of Lateral Inheritance, so it will not make the correct lookups to find the correct CLDR data to use.
Worse yet, `ruby-cldr` doesn't know how to serialize these attributes into YAML, so it doesn't export these data from CLDR at all!

There is not yet a solution for these limitations ([related `ruby-cldr` issue](https://github.com/ruby-i18n/ruby-cldr/issues/117))

## Aliases

[Aliases](http://www.unicode.org/reports/tr35/tr35-31/tr35.html#Alias_Elements) are another complexity used in CLDR to define how to resolve a value.

Aliases are defined in the `root` locale and specify that the client should restart its key lookups in the original locale, this time with a different key.

`ruby-i18n/i18n` (v1.9.0+) does support aliases, through the use of `Symbols`. When a key resolves to a `Symbol`, it will treat it as an alias and restart its lookup from the original locale using the `Symbol` as the new key.

### Aside: Explicit inheritance markers

In the [upstream CLDR repository](https://github.com/unicode-org/cldr), you may come across keys with a value of `↑↑↑`. This is an explicit Locale Inheritance marker.
It allows the upstream maintainers to distinguish between the two reasons why a key might be missing from a locale:

* The CLDR is missing data for that key in that locale (i.e., it's missing data)
* The CLDR is relying on Locale Inheritance to provide the value (i.e., it's intentionally missing a value)

Clever. (It's similar to the difference between `None` and `Nil` in some programming languages) At any rate, the build step in [`cldr-staging`](https://github.com/unicode-org/cldr-staging) removes these values, so you will never see them in the CLDR release ZIPs.

# Summary

* Avoiding duplication in the data is important for upstream CLDR to ensure high data quality.
* Avoiding duplication in the data is important for clients to avoid memory bloat.
* Sometimes it is necessary to flatten the data, trading increased memory and duplication for simpler clients and faster lookups.
