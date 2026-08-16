import XCTest

final class RunnerUITests: XCTestCase {

  func testSignIn() throws {
    let app = XCUIApplication()
    app.launch()

    let usernameField = app.textFields["Username"].firstMatch
    XCTAssertTrue(usernameField.waitForExistence(timeout: 15), "Username field did not appear")
    usernameField.tap()
    if let existing = usernameField.value as? String, !existing.isEmpty {
      let deleteString = String(repeating: XCUIKeyboardKey.delete.rawValue, count: existing.count)
      usernameField.typeText(deleteString)
    }
    usernameField.typeText("brad")

    let passwordPredicate = NSPredicate(format: "label == %@ OR value == %@", "Password", "Password")
    var passwordField = app.descendants(matching: .any).matching(passwordPredicate).firstMatch
    if !passwordField.waitForExistence(timeout: 2) {
      passwordField = app.secureTextFields["Password"].firstMatch
    }
    if !passwordField.waitForExistence(timeout: 2) {
      passwordField = app.textFields["Password"].firstMatch
    }
    if !passwordField.waitForExistence(timeout: 2) {
      passwordField = app.textFields.element(boundBy: 1)
    }
    XCTAssertTrue(passwordField.waitForExistence(timeout: 5), "Password field did not appear")
    passwordField.tap()
    passwordField.typeText("change-me")

    let signInButton = app.buttons["Sign in"].firstMatch
    XCTAssertTrue(signInButton.waitForExistence(timeout: 5), "Sign in button did not appear")
    signInButton.tap()

    sleep(3)
  }
}
