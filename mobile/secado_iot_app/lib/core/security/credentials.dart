import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Credentials {
  final String username, password;
  const Credentials(this.username, this.password);
  bool get complete => username.isNotEmpty && password.isNotEmpty;
}

abstract interface class CredentialStore {
  Future<Credentials> read();
  Future<void> save(Credentials credentials);
  Future<void> clear();
}

class SecureCredentialStore implements CredentialStore {
  final FlutterSecureStorage _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  @override
  Future<Credentials> read() async => Credentials(
        await _storage.read(key: 'mqtt_user') ?? '',
        await _storage.read(key: 'mqtt_password') ?? '',
      );
  @override
  Future<void> save(Credentials credentials) async {
    await _storage.write(key: 'mqtt_user', value: credentials.username);
    await _storage.write(key: 'mqtt_password', value: credentials.password);
  }

  @override
  Future<void> clear() => _storage.deleteAll();
}
