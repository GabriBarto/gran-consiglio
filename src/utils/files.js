import { Platform } from 'react-native';
import { File } from 'expo-file-system';

// Expo SDK 57 makes the WinterCG-compliant `expo/fetch` the global fetch
// (see docs.expo.dev/versions/v57.0.0/sdk/expo — "On native platforms... the
// expo/fetch implementation becomes the global fetch by default"). Its
// FormData is spec-compliant and only knows how to send actual Blob/File
// parts — the classic React Native trick of appending a plain
// { uri, name, type } object (which only the old bridge's Networking module
// understood) is silently rejected, so the request never leaves the device.
// expo-file-system's File class implements Blob and works with it directly.
//
// Shared by every screen that uploads a document picked via
// expo-document-picker (registration, license reupload, shop creation).
//
// On web, expo-file-system is only a stub (its File class has no
// validatePath, so `new File(...)` throws "this.validatePath is not a
// function"). There expo-document-picker already hands us the browser's
// native File object on `asset.file`, which FormData accepts as is.
export function toUploadFile(pickedDocument) {
  if (Platform.OS === 'web') {
    return pickedDocument.file;
  }
  return new File(pickedDocument.uri);
}
