package com.acty.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import com.acty.ActyConfig
import org.json.JSONObject
import java.io.File
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.Signature
import java.time.Instant
import java.util.UUID

/**
 * SessionSigner.kt
 * Creates/uses a Keystore key pair, computes merkle root (or row chain), and signs session manifests.
 */
class SessionSigner(private val context: Context) {
    companion object {
        private const val TAG = "SessionSigner"
    }

    private fun ensureKeyExists() {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (ks.containsAlias(ActyConfig.KEYSTORE_ALIAS)) return

        try {
            val keyPairGenerator = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                KeyPairGenerator.getInstance("ED25519", "AndroidKeyStore")
            } else {
                KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
            }

            val builder = KeyGenParameterSpec.Builder(
                ActyConfig.KEYSTORE_ALIAS,
                KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
            )
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setUserAuthenticationRequired(false)

            if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.S) {
                builder.setAlgorithmParameterSpec(java.security.spec.ECGenParameterSpec("secp256r1"))
            }

            keyPairGenerator.initialize(builder.build())
            keyPairGenerator.generateKeyPair()
            Log.d(TAG, "Keystore key created")
        } catch (e: Exception) {
            Log.e(TAG, "Key generation failure: ${e.message}")
        }
    }

    private fun getSigningKeyStore(): KeyStore.PrivateKeyEntry? {
        try {
            val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            val entry = ks.getEntry(ActyConfig.KEYSTORE_ALIAS, null)
            if (entry is KeyStore.PrivateKeyEntry) return entry
        } catch (e: Exception) {
            Log.e(TAG, "Keystore access failure: ${e.message}")
        }
        return null
    }

    private fun sha256hex(input: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(input)
        return digest.joinToString("") { "%02x".format(it) }
    }

    fun signSession(csvFile: File, sigFile: File, sessionId: String, vehicleId: String, merkleRoot: String): Boolean {
        ensureKeyExists()
        val entry = getSigningKeyStore() ?: return false

        val signatureInstance = try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
                Signature.getInstance("Ed25519")
            } else {
                Signature.getInstance("SHA256withECDSA")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create signature instance: ${e.message}")
            return false
        }

        return try {
            signatureInstance.initSign(entry.privateKey)
            val payload = csvFile.readBytes()
            signatureInstance.update(payload)
            val signatureBytes = signatureInstance.sign()

            val publicKeyBytes = entry.certificate.publicKey.encoded

            val sigJson = JSONObject().apply {
                put("session_id", sessionId)
                put("vehicle_id", vehicleId)
                put("timestamp", Instant.now().toString())
                put("merkle_root", merkleRoot)
                put("signature_b64", Base64.encodeToString(signatureBytes, Base64.NO_WRAP))
                put("public_key_b64", Base64.encodeToString(publicKeyBytes, Base64.NO_WRAP))
            }

            sigFile.writeText(sigJson.toString())
            true
        } catch (e: Exception) {
            Log.e(TAG, "Sign session failed: ${e.message}")
            false
        }
    }
}
