export interface UserResponse {
  id: string
  username: string
  email: string
  relationship_level: number
}

export interface Token {
  access_token: string
  token_type: string
}

export interface RegisterInput {
  username: string
  email: string
  password: string
}
