import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config/api_config.dart';

class AuthService {
  static const _tokenKey = 'sirisos_access_token';
  static String? _token;

  static String? get token => _token;

  static Map<String, String> get authorizationHeaders =>
      _token == null ? const {} : {'Authorization': 'Bearer $_token'};

  Future<bool> restoreSession() async {
    final preferences = await SharedPreferences.getInstance();
    _token = preferences.getString(_tokenKey);
    if (_token == null) return false;

    final response = await http
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/auth/me'),
          headers: authorizationHeaders,
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 200) return true;
    await logout();
    return false;
  }

  Future<void> login({required String username, required String password}) async {
    final response = await http
        .post(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/auth/login'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'username': username, 'password': password}),
        )
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 200) {
      throw const AuthException('Incorrect username or password.');
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['access_token'] is! String) {
      throw const AuthException('The server returned an invalid login response.');
    }

    _token = decoded['access_token'] as String;
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_tokenKey, _token!);
  }

  Future<void> logout() async {
    _token = null;
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_tokenKey);
  }
}

class AuthException implements Exception {
  const AuthException(this.message);
  final String message;
  @override
  String toString() => message;
}
