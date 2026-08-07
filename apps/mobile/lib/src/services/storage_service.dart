import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/storage_snapshot.dart';
import 'auth_service.dart';

class StorageService {
  StorageService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<StorageSnapshot> fetchSnapshot() async {
    final response = await _client
        .get(
          Uri.parse('${ApiConfig.baseUrl}/api/v1/homelab/storage'),
          headers: AuthService.authorizationHeaders,
        )
        .timeout(const Duration(seconds: 6));
    if (response.statusCode == 401) {
      throw const StorageServiceException('Your session has expired.');
    }
    if (response.statusCode != 200) {
      throw StorageServiceException(
        'Storage request failed with status ${response.statusCode}.',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const StorageServiceException('Invalid storage response.');
    }
    return StorageSnapshot.fromJson(decoded);
  }
}

class StorageServiceException implements Exception {
  const StorageServiceException(this.message);
  final String message;

  @override
  String toString() => message;
}
