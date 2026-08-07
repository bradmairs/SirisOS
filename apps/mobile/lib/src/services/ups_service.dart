import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/ups_snapshot.dart';
import 'auth_service.dart';

class UpsService {
  UpsService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<UpsSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/ups'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 6));
    if (response.statusCode == 401) {
      throw const UpsServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw UpsServiceException(
        'UPS request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const UpsServiceException('Invalid UPS response.');
    }
    return UpsSnapshot.fromJson(decoded);
  }
}

class UpsServiceException implements Exception {
  const UpsServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
