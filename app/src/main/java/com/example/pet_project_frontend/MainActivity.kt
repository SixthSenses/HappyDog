// 깃허브 코드 테스트용 !!!!!!!!!!!!!!!!!!!!
package com.example.pet_project_frontend

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.example.pet_project_frontend.core.theme.PetCareTheme
import com.example.pet_project_frontend.presentation.mypage.main.MyPageScreen
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PetCareTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    // 임시로 MyPageScreen 표시
                    MyPageScreen()
                }
            }
        }
    }
}
