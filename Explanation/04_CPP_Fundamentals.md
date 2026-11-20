# 04 · C++ Fundamentals: TestTrust

**Rule:** only the C++ ideas this project's code actually relies on, each with a tiny example first and then where it appears in our code. This file grows with every step. (Current to S1.)

---

## 1. A `struct` of `static` functions

```cpp
struct FMathRules
{
	static int Twice(int X) { return 2 * X; }   // no object needed: FMathRules::Twice(3)
};
```
- A `static` member function belongs to the type, not to an object, so it has no `this` and can't touch per-object data.
- *Why not free functions in a namespace?* Both work. A struct groups the rules under one name that reads well at the call site (`FTTSampleRules::ComputeDamage`) and follows UE's `F` prefix for plain types. A namespace would be equally valid; we follow the struct style UE uses for helpers like `FMath`.
- **In our code:** `FTTSampleRules` has three static rules. Pure functions with no state are the easiest code to test: the same inputs always give the same output, and no world or object has to exist.

## 2. `static constexpr` data members

```cpp
struct FLimits { static constexpr int Max = 10; };   // a compile-time constant, one per type
```
- `constexpr` means "known at compile time", so the compiler can fold it into every use.
- Since C++17 a `static constexpr` data member is implicitly `inline`: it can live in a header without a separate definition in a `.cpp`, and without an export macro across DLLs.
- **In our code:** `FTTSampleRules::MinDamage = 1`. The tests compare against the same constant the rule uses, so changing the rule's minimum can't silently break a test's expectation. Because it lives in a header, the mutation runner never changes it (headers are not mutated, `02` §7).

## 3. Pass by value vs by `const` reference

```cpp
int Add(int A, int B);                                  // small values: copy them
double Dist(const FVector& A, const FVector& B);        // larger objects: read them through a reference
```
- Copying an `int32`, `float` or `bool` is as cheap as passing a pointer, so they are passed by value.
- An `FVector` is three `double`s (24 bytes). `const FVector&` avoids the copy and promises not to change the caller's vector.
- **In our code:** `ComputeDamage(int32, int32, bool)` by value; `IsInRange(const FVector&, const FVector&, double)`.

## 4. The conditional operator `?:`

```cpp
const float Clamped = Value > 0.f ? Value : 0.f;   // one expression, two results
```
- `Condition ? A : B` evaluates to `A` if the condition is true, otherwise `B`. Unlike `if`, it is an expression, so it can initialise a `const`.
- **In our code:** `TickCooldown` returns `Next > 0.f ? Next : 0.f`. The mutation runner changes the `>` (ROR), not the `?:` itself.

## 5. Compound assignment

```cpp
Damage *= 2;   // the same as Damage = Damage * 2;
```
- **In our code:** the critical hit in `ComputeDamage`. Two mutants come from this one line: `*=` → `/=` (AOR) and deleting the whole statement (SDL).

## 6. Header guards with `#pragma once`

```cpp
#pragma once   // this header's contents are included at most once per .cpp
```
- Without it, a header included twice (directly and through another header) would declare everything twice and fail to compile.
- **In our code:** `TTSampleRules.h`. Every UE header uses `#pragma once`; the older `#ifndef X / #define X / #endif` guard is equivalent but noisier.

## 7. Preprocessor conditions: `#if WITH_DEV_AUTOMATION_TESTS`

```cpp
#if WITH_DEV_AUTOMATION_TESTS
	// compiled only when the build defines the macro as 1
#endif
```
- The preprocessor runs before the compiler. Code inside a false `#if` is removed entirely: it costs nothing in the binary.
- **In our code:** the whole test file. UnrealBuildTool defines `WITH_DEV_AUTOMATION_TESTS=1` for Development and Debug builds and `0` for Test and Shipping (`01b #7`), so the tests never ship.
- The mutation lexer skips preprocessor lines, so it never mutates an `#if` (`tt_mutants.py`).

## 8. A `namespace` for file-local helpers, and `constexpr` variables

```cpp
namespace MyTests { constexpr int Flags = 3; }   // MyTests::Flags; no clash with another file's Flags
```
- A named namespace keeps the helper's name from colliding with other files in the same module (UE modules can be unity-built, which pastes several `.cpp` files into one; then two files' helpers would clash).
- **In our code:** `TTSampleTests::Flags`, the test flags shared by all six tests.

## 9. Static objects that run code before `main`

```cpp
struct FRegister { FRegister() { /* add myself to a list */ } };
static FRegister GAutoRegister;   // its constructor runs when the module is loaded
```
- A global or namespace-scope object is constructed when its module (DLL) loads, before any of the module's functions are called.
- **In our code:** `IMPLEMENT_SIMPLE_AUTOMATION_TEST` declares a test class **and** one static instance of it (`AutomationTest.h:4297–4302`). That instance's constructor registers the test by name with the automation framework. This is why a test exists as soon as the module loads, and why the runner must start a **fresh process** per mutant: the registered tests are from the DLL that was loaded at startup.

## 10. Export macros: `#define UE_API TESTTRUSTSAMPLE_API`

```cpp
#define UE_API MYMODULE_API          // MYMODULE_API = dllexport while building MyModule, dllimport for its users
struct FThing { static UE_API void Go(); };
#undef UE_API
```
- In editor builds every module is a DLL. A function in one DLL can be called from another only if it is **exported**. UBT defines `<MODULE>_API` for each module (export inside it, import elsewhere).
- 5.8 headers use a local `UE_API` alias, then `#undef` it at the end of the header so the short name doesn't leak into files that include it (UE5-UpdateBudget's `01b` §3 found this convention in `SignificanceManager.h:8`).
- **In our code:** each `FTTSampleRules` function is `UE_API`, so the tests (in the same module today) or any other module could call them. Only the functions need it; the `constexpr` member doesn't (see §2).

## 11. Integer and floating-point comparison details that matter for mutants

```cpp
float Next = 0.1f - 0.5f;   // -0.4f
Next > 0.f;                 // false
-0.0f == 0.0f;              // true: negative zero compares equal to zero
```
- **Equivalent mutants come from these details.** In `TickCooldown`, `Next > 0.f` → `Next >= 0.f` only differs when `Next` is exactly zero, and then both branches return zero (or negative zero, which compares equal). No test can tell them apart: the mutant is *equivalent* (`02` §4.4).
- Comparing floats with `TestEqual` uses a tolerance (`UE_KINDA_SMALL_NUMBER` by default, `AutomationTest.h:1988`), so `0.75f` computed as `1.0f - 0.25f` passes even with rounding.

## 12. `enum class` with an underlying type

```cpp
enum class EColour : uint8 { Red, Green };   // scoped: EColour::Red; one byte; no silent conversion to int
int X = EColour::Red;                        // compile error: you must write static_cast<int>(EColour::Red)
```
- A plain `enum` leaks its names into the surrounding scope and converts to `int` silently, so two enums with a `None` clash and comparisons between unrelated enums compile.
- `: uint8` fixes the size, which matters when the value is stored per object or sent over a network.
- **In our code:** `ETTProbeEvent` (`None`, `Start`, `Stop`) and the private `FTTProbeWindow::EPhase`.

## 13. A class body is "complete" inside its own member functions

```cpp
struct FCounter
{
	bool IsHigh() const { return Level == ELevel::High; }   // uses ELevel and Level, declared further down: fine
private:
	enum class ELevel : uint8 { Low, High };
	ELevel Level = ELevel::Low;
};
```
- The compiler reads inline member-function bodies as if they were written after the whole class, so they may use members and nested types declared later. (A *declaration*, such as a member's type, still needs the name declared before it.)
- **In our code:** `FTTProbeWindow::IsCapturing()` sits in the public section, above the private `EPhase` it compares against, so the public interface reads first.

## 14. `switch` with a `default`

```cpp
switch (Event) { case E::Start: Begin(); break; case E::Stop: End(); break; default: Idle(); break; }
```
- Each `case` needs its `break`, or execution falls through into the next one.
- **In our code:** `UTTProbeSubsystem::Tick` switches on the window's event; the exit countdown lives in `default`, so it runs on ordinary frames only, never on the `BenchEnd` frame itself.
